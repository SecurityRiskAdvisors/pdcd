import tempfile
from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING
from docker.errors import ImageNotFound
import pathlib
import shlex
import tarfile
from enum import Enum, auto

from .external import FileRegistryClient
from .settings import global_settings
from .log import logger

if TYPE_CHECKING:
    from .config import Config


class ImageOS(Enum):
    Windows = auto()
    Linux = auto()


@dataclass
class RoutineArg:
    key: str


@dataclass
class Routine:
    # class that config-provided payloads get instantiated to
    name: str
    image: str
    config: "Config"
    cli: str = field(default="")
    artifacts: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    store: str = None

    def __hash__(self):
        return hash(self.name)

    def __post_init__(self):
        self._check_image()

        # list of files to cleanup
        # main use is for files created during cli token resolution
        self.cleanup_files: List[str] = []

        cli = []
        for token in shlex.split(self.cli):
            # if, after being split, the token still has a space it needs to be split and resolved on its own. this is primarily meant for situations with nested command lines such as bash -c "<cli>"
            if " " in token:
                new_token = []
                for t in shlex.split(token):
                    new_token.append(self._convert_cli_token(token=t))
                cli.append(" ".join(new_token))
            else:
                cli.append(self._convert_cli_token(token=token))

        self.cli = shlex.join(cli)

        # store should happen AFTER cli token resolution to support use of
        # @artifact + store, otherwise artifacts from @artifact wont be present
        if self.store is not None:
            if len(self.artifacts) != 1:
                raise Exception("Must have exactly 1 artifact when using store")

            filereg: FileRegistryClient = self.config.client_manager.get_client_by_name("files").client
            filereg.upsert_file(name=self.store, value=self.artifacts[0], payload=self.name)

    def _convert_cli_token(self, token: str):
        # token should look like '@foo::bar-baz'
        if token.startswith("@") and "::" in token:
            connector_name, args = token.split("::")
            connector_name = connector_name[1:]  # remove starting '@'

            client = self.config.client_manager.get_client_by_name(connector_name)

            resolved_token, cleanup_files = client.client.resolve_token(
                token=args, file_dir=self.config.file_dir, connector_name=connector_name, routine=self
            )

            self.cleanup_files.extend(cleanup_files)
            return resolved_token
        else:
            return token

    def _check_image(self):
        """check that image is available to Docker client"""
        docker = self.config.get_docker_client()
        try:
            docker.images.get(self.image)
        except ImageNotFound:
            raise Exception(f'Unknown image "{self.image}"')

    def cleanup(self):
        for f in self.cleanup_files:
            pathlib.Path(f).unlink(missing_ok=True)

    @property
    def image_os(self) -> ImageOS:
        docker = self.config.get_docker_client()
        image = docker.images.get(self.image)
        imageos = image.attrs.get("Os").lower()  # this capitalization...
        return ImageOS.Windows if imageos == "windows" else ImageOS.Linux

    def run_ctr(self):
        docker = self.config.get_docker_client()

        if self.image_os == ImageOS.Windows:
            bind_dir = "c:/shared"
            network = "nat"  # https://techcommunity.microsoft.com/t5/itops-talk-blog/docker-host-network-alternatives-for-windows-containers/ba-p/3390115
            memswap = None  # Docker on Windows does not support swap
        else:
            bind_dir = "/shared"
            network = "host"
            memswap = global_settings.docker_memswap_limit

        labels = {"pdcd": "true"}  # values need to stay as strings
        if self.config.remote_build:
            # when running remote, tag container with aws caller arn
            #   this should include the users email as the role session name
            #   and it can be used for filtering results when retrieving logs
            labels["aws_arn"] = self.config.remote_client.fwd_params.aws_arn

        ctr = docker.containers.run(
            image=self.image,
            auto_remove=False,
            remove=False,
            network_mode=network,
            command=self.cli,
            volumes={self.config.mnt_dir: {"bind": bind_dir, "mode": "rw"}},
            detach=True,
            mem_limit=global_settings.docker_mem_limit,
            memswap_limit=memswap,
            # oom_kill_disable=True,
            labels=labels,
            # golang specific soft resource limit for golang >= v1.19
            # environment={"GOMEMLIMIT":"1GiB"}
        )
        ctr.wait()
        ctr_dir = ctr.attrs["Config"]["WorkingDir"]
        for artifact in self.artifacts:
            ctr_artifact = artifact
            if self.image_os == ImageOS.Windows:
                # normal pathlib paths do not handle windows drive letters so need to use purewindowspath instead
                artifact_o = pathlib.PureWindowsPath(artifact)
            else:
                artifact_o = pathlib.Path(artifact)
                if not artifact.startswith("/"):
                    ctr_artifact = f"{ctr_dir}/{artifact}"

            try:
                tarstream, stats = ctr.get_archive(ctr_artifact)
            except Exception as e:
                logger.error(f"Unknown artifact {ctr_artifact} in container {ctr.short_id}")
                raise e
            tarf = tempfile.mkstemp(suffix=".tar")[1]
            tarf_o = pathlib.Path(tarf)
            with tarf_o.open("wb") as f:
                for chunk in tarstream:
                    f.write(chunk)
            tar = tarfile.open(tarf)
            artifact_member = tar.extractfile(tar.getmember(artifact_o.name))
            tarf_o.unlink()

            # pathlib.Path(f"{self.config.file_dir}/{artifact_o.name}").write_bytes(artifact_member.read())
            self.config.file_manager.write(content=artifact_member.read(), filename=artifact_o.name)

        if self.config.cleanup:
            ctr.remove()

    @classmethod
    def run(cls, *constructor_args, **constructor_kwargs):
        cls(*constructor_args, **constructor_kwargs).run_ctr()
