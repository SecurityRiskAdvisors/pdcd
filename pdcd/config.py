from dataclasses import dataclass, field
import desert
import yaml
import pathlib
import tempfile
import os
import shutil
from typing import List, Optional, TYPE_CHECKING, Any
from docker.client import DockerClient as DockerSDKClient

from .external import DockerClient, FileRegistryClient, ArtifactClient
from .files import set_fm_for_config
from .connectors import convert_connector_dict_to_clients, RemoteBuildClient, ClientManager
from .log import logger
from .settings import global_settings

if TYPE_CHECKING:
    from .files import SMBFileManager


@dataclass
class PayloadConfig:
    name: str
    image: str
    cli: str = field(default="")
    artifacts: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    store: str = None


class UserSharedConfigs:
    def __init__(self):
        from .settings import global_settings

        self._connector_file = global_settings.connectors_file

        self.shared_clients = None
        if self._connector_file.exists():
            # the expected format of this file is the same as the connectors section of the
            # standard config file
            # e.g.  connectors:
            #         name: ...
            connectors_o = yaml.safe_load(self._connector_file.read_text())
            connectors_dict = connectors_o.get("connectors")
            self.shared_clients = convert_connector_dict_to_clients(connector_dict=connectors_dict)
            logger.info(f"Loaded shared connectors from {self._connector_file.resolve().as_posix()}")


@dataclass
class Config:
    payloads: List[PayloadConfig]
    connectors: Optional[Any]
    file_dir: str = field(default_factory=tempfile.mkdtemp)
    cleanup: bool = True
    workers: int = 2
    settings: Any = None

    @classmethod
    def from_file(cls, path: str) -> "Config":
        path = pathlib.Path(path)
        # setattr(cls, "original_file_path", path.resolve())
        data = yaml.safe_load(path.read_text())
        return desert.schema(cls).load(data)

    def _process_settings(self):
        if self.settings is None:
            return
        for k, v in self.settings.items():
            if hasattr(global_settings, k):
                setattr(global_settings, k, v)

    def __post_init__(self):
        self._process_settings()

        self.remote_build = False
        self.mnt_dir = self.file_dir
        self.file_manager = None
        docker_client_args = {}

        if not os.access(self.file_dir, os.W_OK):
            raise Exception(f"File directory {self.file_dir} not writable")

        self.client_manager = ClientManager()

        if self.connectors is not None:
            self.client_manager.upsert_clients_from_manager(
                manager=convert_connector_dict_to_clients(connector_dict=self.connectors)
            )

        # shared configs should override config-level connector settings
        # so global config is read after config-level connectors
        shared_configs = UserSharedConfigs()
        if shared_configs.shared_clients is not None:
            self.client_manager.upsert_clients_from_manager(manager=shared_configs.shared_clients)

        remote_clients = self.client_manager.get_clients_by_type(client_type=RemoteBuildClient)
        if len(remote_clients) > 0:
            # remote build requires local SSM session manager plugin
            # https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
            if shutil.which("session-manager-plugin") is None:
                raise Exception("AWS SSM session manager plugin required")

            self.remote_build = True
            # connector class is marked unique so there should only be 1 result
            self.remote_client: RemoteBuildClient = remote_clients[0].client

            # port forward occurs on a local high port to a Docker daemon port on the build server
            # the local env var DOCKER_HOST is a convenient way to override the default behavior
            #   note: the default Docker client is created using the from_env method
            #   so it will use this env var
            env = dict(os.environ)
            env["DOCKER_HOST"] = self.remote_client.docker_env_string
            docker_client_args["environment"] = env
            self.remote_client.start_forwarding()

            # usually there is no difference b/w where artifacts are written and whats mounted since its all local
            # however, when the builder is remote, the mount volume will differ from the file_dir since the
            # mount is relative to the remote systems and the file_dir is relative to the controller
            # a random uuid is used to help limit inadvertent collisions and file commingling
            self.mnt_dir = self.remote_client.mnt_dir + "/" + self.remote_client.fwd_params.smb_uuid

        # this should occur after checking for the remote connector to ensure that
        # the Docker env is set
        self.init_default_clients(docker_args=docker_client_args)

        set_fm_for_config(self)
        if self.remote_build:
            self.file_manager: SMBFileManager
            self.file_manager.mkdir(self.remote_client.fwd_params.smb_uuid)

    def init_default_clients(self, docker_args: dict = None):
        # default clients for all runs of tool, regardless of user-provided connectors
        # - docker for default docker client
        # - files for storing artifacts for other jobs
        # - artifacts for noting CLI paths should be added to artifact list
        docker_args = docker_args if docker_args is not None else {}
        self.client_manager.upsert_client(client_name="docker", client=DockerClient(**docker_args))
        self.client_manager.upsert_client(client_name="files", client=FileRegistryClient())
        self.client_manager.upsert_client(client_name="artifact", client=ArtifactClient())

    def cleanup_resources(self):
        # delete remote directory and stop port forwards
        # TODO: should run on all exits, incl. failed runs
        if self.remote_build:
            for (func, kwargs) in [
                (self.file_manager.rmdir, {"directory": self.remote_client.fwd_params.smb_uuid}),
                (self.remote_client.stop_forwarding, {}),
            ]:
                try:
                    func(**kwargs)
                except:
                    pass

    def get_docker_client(self) -> DockerSDKClient:
        """convenience function for getting Docker client"""
        return self.client_manager.get_client_by_name("docker").client.docker
