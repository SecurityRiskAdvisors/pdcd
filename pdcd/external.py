import time
import pathlib
import tempfile
import docker
import string
import random
import boto3
import subprocess
import json
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING, Tuple
import mythic.mythic as mythic_sdk
import asyncio
from abc import ABC, abstractmethod
import base64
from functools import lru_cache

from .shellcode import Shellcode
from .log import logger
from .utils import shell, find_free_local_port, generate_uuid, pad_list, file_is_empty
from .settings import global_settings

if TYPE_CHECKING:
    from .routines import Routine

ARTIFACT_PAYLOAD_EXT = {
    "dll": ".dll",
    "exe": ".exe",
    "powershell": ".ps1",
    "python": ".py",
    "raw": ".bin",
    "svcexe": ".exe",
    "sc": ".bin",
}


class ClientABC(ABC):
    @abstractmethod
    def resolve_token(self, token: str, file_dir: str, connector_name: str, **kwargs) -> Tuple[str, list]:
        # this method is used to resolve a payload CLI
        # it should take the token and file directory for writing as input
        # it should return the resoved value and a list of cleanup files
        # connector name is used for caching
        # args/kwargs are for client specific logic
        pass


class CobaltStrikeClient(ClientABC):
    # This client generates temporary Cortana scripts to execute functions against a teamserver
    # It relies on the agscript script inside a standard install and requires that the installation
    # is properly licensed first
    def __init__(self, host: str, password: str, port: str = "50050", install_dir: str = "/opt/cobaltstrike"):
        self.__host = host
        self.__port = port
        self.__password = password

        # this client will connect to a teamserver with a username in the format:
        # pdcd_<timestamp>_<random string>
        epoch = str(int(time.time()))
        rand_str = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        self.__user = f"pdcd_{epoch}_{rand_str}"

        self.__install_dir = install_dir

    def resolve_token(self, token: str, file_dir: str, connector_name: str, **kwargs):
        # token format: < STAGED / STAGELESS > [PS] - < 64 / 86 > - < LISTENER > -[B64]
        # examples:
        #   x64 stageless shellcode using HTTPS listener: STAGELESS-64-HTTPS
        #   x64 stageless PowerShell using HTTP listener: STAGELESSPS-64-HTTPS
        #   base-64 encoded x86 staged shellcode using HTTPS listener: STAGED-86-HTTPS-B64

        token_parts = token.split("-")
        token_parts = pad_list(token_parts, None, 4)
        artifact, arch, listener, postproc = token_parts

        scformat = "raw"
        if artifact.endswith("PS"):
            scformat = "powershell"
            artifact = artifact[:-2]
        artifact = artifact.lower() == "stageless"

        sc = self.export_shellcode(arch=f"x{arch}", listener=listener, stageless=artifact, scformat=scformat)

        if postproc == "B64":
            sc = Shellcode(shellcode=base64.b64encode(sc.shellcode))

        binfile = tempfile.mkstemp(dir=file_dir, suffix=ARTIFACT_PAYLOAD_EXT[scformat])[1]
        sc.to_file(path=binfile)

        cleanup_files = [binfile]
        binfile_o = pathlib.Path(binfile)

        # whether remote or local, mounted path should always be /shared
        resolved_token = f"/shared/{binfile_o.name}"
        logger.info(f"Resolved token {token} to value {resolved_token} for {type(self).__name__}")

        return resolved_token, cleanup_files

    def validate_credentials(self):
        """validates provided credentials against a teamserver by connecting then disconnecting"""
        tmp_cna = tempfile.mkstemp(suffix=".cna")[1]
        snippet = "on ready { closeClient(); }"  # do nothing
        pathlib.Path(tmp_cna).write_text(snippet)
        cmd = ["bash", "agscript", self.__host, self.__port, self.__user, self.__password, tmp_cna]
        output = shell(cli=cmd, cwd=self.__install_dir).decode()
        pathlib.Path(tmp_cna).unlink()

        # cant use exit code as it returns 0 even if the connection fails (as of CS >= 4.7.2)
        # TODO: add error code for version mismatch
        for error in ["Connection refused", "authentication failure", "User is already connected"]:
            if error in output:
                raise Exception(f"Cannot connect to teamserver. Error: {error.lower()}")

        logger.info(f"Validatd credentials for {type(self).__name__} against {self.__user}@{self.__host}:{self.__port}")

    @lru_cache(maxsize=None)
    def export_shellcode(self, arch: str, listener: str, stageless: bool = True, scformat: str = "raw") -> Shellcode:
        # this function is cached to improve performance when repeatedly using the same CLI token
        # this client announces in the teamserver event log when it connects/disconnects

        self.validate_credentials()

        tmp_cna = tempfile.mkstemp(suffix=".cna")[1]
        tmp_bin = tempfile.mkstemp(suffix=ARTIFACT_PAYLOAD_EXT[scformat])[1]
        artifact_type = "artifact_payload" if stageless else "artifact_stager"
        snippet = f"""
            on ready {{
                elog('PDCD: exporting shellcode');
                local('$data $handle');
                $data = {artifact_type}('{listener}', '{scformat}', '{arch}');
                $handle = openf('>{tmp_bin}');
                writeb($handle, $data);
                closef($handle);
                closeClient();
            }}
            """
        pathlib.Path(tmp_cna).write_text(snippet)

        cmd = ["bash", "agscript", self.__host, self.__port, self.__user, self.__password, tmp_cna]
        resp = shell(cli=cmd, cwd=self.__install_dir).decode()
        # TODO: this error and errors in validate creds function should be maintained outside class
        if "java.lang.RuntimeException" in resp and "No listener" in resp:
            raise Exception(f"Unknown listener: {listener}")

        sc = Shellcode.from_file(src=tmp_bin)

        empty = file_is_empty(tmp_bin)
        pathlib.Path(tmp_cna).unlink()
        pathlib.Path(tmp_bin).unlink()

        if empty:
            raise Exception(f"Temp shellcode file {tmp_bin} is empty")

        return sc


class MythicClient(ClientABC):
    def __init__(
        self,
        host: str,
        password: str,
        callback_url: str,  # http://example.com
        callback_port: str,
        port: str = "7443",  # management port
        user: str = "neo",
    ):
        self.__host = host
        self.__port = port
        self.__password = password
        self.__user = user
        self.__callback_url = callback_url
        self.__callback_port = callback_port

    def resolve_token(self, token: str, file_dir: str, connector_name: str, **kwargs) -> Tuple[str, list]:
        # token format: < ARTIFACT > - < PROFILE >
        # example:
        #   Exe using HTTPS callback: EXE-HTTP
        token_parts = token.split("-")
        artifact, profile = token_parts

        scformat = "Shellcode"
        if artifact == "EXE":
            scformat = "WinExe"
        extension = ".bin" if scformat == "Shellcode" else ".exe"

        sc = self.export_shellcode(profile=profile, scformat=scformat)
        binfile = tempfile.mkstemp(dir=file_dir, suffix=extension)[1]
        sc.to_file(path=binfile)

        cleanup_files = [binfile]
        binfile_o = pathlib.Path(binfile)

        resolved_token = f"/shared/{binfile_o.name}"
        logger.info(f"Resolved token {token} to value {resolved_token} for {type(self).__name__}")

        return resolved_token, cleanup_files

    @lru_cache(maxsize=None)
    def export_shellcode(self, profile: str, scformat: str = "Shellcode") -> Shellcode:
        mythic = asyncio.run(
            mythic_sdk.login(
                username=self.__user,
                password=self.__password,
                server_ip=self.__host,
                server_port=int(self.__port),
                ssl=True,
                timeout=-1,
            )
        )

        # mythic payload settings are defined per payload rather than per listener,
        #   meaning you need to provide them via this tool
        #   default values are provided here but some can be overridden via env vars
        if profile.lower() == "smb":
            build_vars = {
                "pipename": global_settings.mythic_smb_pipename,
                "killdate": "2030-10-12",
                "encrypted_exchange_check": "T",
            }
        else:
            build_vars = {
                "callback_host": self.__callback_url,
                "callback_interval": global_settings.mythic_callback_interval,
                "c2_profile": profile.lower(),
                "AESPSK": "aes256_hmac",
                "get_uri": global_settings.mythic_http_geturi,
                "post_uri": global_settings.mythic_http_posturi,
                "query_path_name": global_settings.mythic_http_queryuri,
                "proxy_host": "",
                "proxy_port": "",
                "proxy_user": "",
                "proxy_pass": "",
                "callback_port": self.__callback_port,
                "killdate": "2030-10-12",
                "encrypted_exchange_check": True,
                "callback_jitter": global_settings.mythic_jitter_percent,
                "headers": {"User-Agent": global_settings.mythic_http_useragent},
            }

        payload = asyncio.run(
            mythic_sdk.create_payload(
                # TODO: currently hardcoded but should make configurable
                #   this will require different configs for different payloads
                mythic=mythic,
                payload_type_name="apollo",
                operating_system="Windows",
                c2_profiles=[{"c2_profile": profile.lower(), "c2_profile_parameters": build_vars}],
                build_parameters=[{"name": "output_type", "value": scformat}],
                description="Built with PDCD",
                filename="pdcd",
                return_on_complete=True,
                include_all_commands=True,
            )
        )
        payload_contents = asyncio.run(mythic_sdk.download_payload(mythic=mythic, payload_uuid=payload.get("uuid")))
        # note: cannot delete payloads as mythic does not allow spawning from dead payloads
        if len(payload_contents) == 0:
            raise Exception(f"Shellcode is empty")
        return Shellcode(shellcode=payload_contents)


@dataclass
class AWSPortForwardParams:
    instance_id: str
    bind_port: int
    target_port: int


class AWSPortForwardHandler:
    # This class is used to manage port forwards via AWS SSM
    # AWS SSM port forwards require the AWS SSM session manager plugin
    # If looking at the AWS SSM session list in the AWS console/SSM API, sessions created by this
    #   tool will be noted as such in the description
    # Once the port forward is started via this class, the associated session manager process
    #   will also be tracked
    def __init__(self, profile: str, region: str, instance_id: str, bind_port: int, target_port: int):
        self._session = boto3.session.Session(profile_name=profile, region_name=region)
        self._ssm_client = self._session.client("ssm")
        self._params = AWSPortForwardParams(instance_id=instance_id, bind_port=bind_port, target_port=target_port)

        self.process: Optional[subprocess.Popen] = None
        self.session_id: Optional[str] = None

    def start(self):
        res: dict = self._ssm_client.start_session(
            Target=self._params.instance_id,
            DocumentName="AWS-StartPortForwardingSession",
            Reason="PDCD Remote - Port Forward",
            Parameters={
                "portNumber": [str(self._params.target_port)],
                "localPortNumber": [str(self._params.bind_port)],
            },
        )

        command = [
            "session-manager-plugin",
            json.dumps(res),
            self._ssm_client.meta.region_name,
            "StartSession",
            self._session.profile_name,
            json.dumps({"Target": self._params.instance_id}),
            self._ssm_client.meta.endpoint_url,
        ]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        self.process = proc
        self.session_id = res.get("SessionId")

        logger.info(
            f"Started port forward on local port {self._params.bind_port} for session {self.session_id} to instance {self._params.instance_id}"
        )

    def stop(self):
        if self.process:
            self.process.terminate()
        else:
            logger.warn(f"Attempted to terminate nonexistent process (PID {self.process.pid})")

        if self.session_id:
            self._ssm_client.terminate_session(SessionId=self.session_id)
        else:
            logger.warn(f"Attempted to terminate nonexistent SSM session (ID: {self.session_id})")


def get_aws_caller_arn(profile: str, region: str) -> str:
    session = boto3.session.Session(profile_name=profile, region_name=region)
    return session.client("sts").get_caller_identity()["Arn"]


@dataclass
class RemoteBuildParameters:
    aws_arn: str
    # values for misc remote-related operations
    smb_uuid: str = field(default_factory=generate_uuid)
    # env controllable items
    docker_target_port: int = global_settings.docker_target_port
    docker_bind_port: int = global_settings.docker_bind_port
    smb_target_port: int = global_settings.smb_target_port
    smb_bind_port: int = global_settings.smb_bind_port
    smb_share_name: str = global_settings.smb_share_name


class RemoteBuildClient:
    # Any server can be used as a remote build server as long as it meets the following requirements:
    # - SMB server with anonymous write access on the share
    #   - share name configured via RemoteBuildParameters.smb_share_name
    #   - port configured RemoteBuildParameters.smb_target_port
    # - Docker daemon bound to TCP port (localhost is fine)
    #   - port configured RemoteBuildParameters.docker_target_port
    # - AWS SSM agent and principal authorized to create/delete sessions
    def __init__(
        self,
        aws_instance_id: str,
        aws_profile: str,
        mnt_dir: str,
        fwd_params: RemoteBuildParameters = None,
        aws_region: str = "us-east-1",
    ):
        if fwd_params is None:
            self.fwd_params = RemoteBuildParameters(aws_arn=get_aws_caller_arn(profile=aws_profile, region=aws_region))
        else:
            self.fwd_params = fwd_params

        self._docker_port_fwd = AWSPortForwardHandler(
            profile=aws_profile,
            region=aws_region,
            instance_id=aws_instance_id,
            bind_port=self.fwd_params.docker_bind_port,
            target_port=self.fwd_params.docker_target_port,
        )
        self._smb_port_fwd = AWSPortForwardHandler(
            profile=aws_profile,
            region=aws_region,
            instance_id=aws_instance_id,
            bind_port=self.fwd_params.smb_bind_port,
            target_port=self.fwd_params.smb_target_port,
        )

        self.mnt_dir = mnt_dir

    @property
    def docker_env_string(self) -> str:
        return f"tcp://127.0.0.1:{self.fwd_params.docker_bind_port}"

    def start_forwarding(self):
        self._docker_port_fwd.start()
        self._smb_port_fwd.start()
        # TODO: check connections are live
        time.sleep(3)  # TODO: theres prob a better way for this

    def stop_forwarding(self):
        self._docker_port_fwd.stop()
        self._smb_port_fwd.stop()


class DockerClient:
    def __init__(self, **kwargs):
        self.docker = docker.from_env(**kwargs)

    def get_ctr_logs_by_imagename(
        self, image: str, filter_args: dict = None, list_args: dict = None, aws_arn: str = None
    ) -> dict:
        # arguments to pass to Docker container list API
        list_args = {} if not list_args else list_args
        # arguments to pass to Docker container list filter
        filter_args = {} if not filter_args else filter_args
        # default filter is to only look at exited containers originating from the provided image
        filter_args = {**filter_args, "status": "exited", "ancestor": image}
        ctrs = self.docker.containers.list(all=True, filters=filter_args, **list_args)
        results = {}
        for ctr in ctrs:
            # only consider PDCD generated containers, which are tagged as such
            if ctr.labels.get("pdcd") == "true":
                values = {"image": ctr.image.tags[0], "logs": ctr.logs()}
                if aws_arn:
                    if ctr.labels.get("aws_arn") == aws_arn:
                        results[ctr.short_id] = values
                else:
                    results[ctr.short_id] = values
        return results


class FileRegistryClient(ClientABC):
    # this is a builtin client that allows for easier dependency management for files between payloads
    # using this client in a payload CLI lets you perform two actions:
    #   store: saves a single artifact name (with the payload name) for future use
    #   @files: CLI token to add the stored file AND the dependency on that files job
    def __init__(self):
        self.__registry = {}  # name: value, payload_name

    def resolve_token(self, token: str, file_dir: str, connector_name: str, **kwargs) -> Tuple[str, list]:
        # token format: < file name >
        if (entry := self.__registry.get(token, None)) is not None:
            routine: Routine
            if (routine := kwargs.get("routine")) is not None:
                routine.dependencies.append(entry[1])
            resolve_token: str = entry[0]
            if not resolve_token.startswith("/shared"):
                # TODO: this makes somes assumptions of the shared drive, namely that it is a single level
                # the extracted artifact from the parent job will only be accessible from the shared drive so the value needs to be updated to add the /shared prefix
                resolve_token = f"/shared/{resolve_token.split('/')[-1]}"
            return resolve_token, []
        else:
            raise Exception(f"Unknown stored file {token}")

    def upsert_file(self, name: str, value: str, payload: str):
        self.__registry[name] = (value, payload)


class ArtifactClient(ClientABC):
    # this is a builtin client that allows for easier alignment between artifacts in the command line
    #   and the artifact list
    # when using this CLI token, the provided value gets appended to the artifact list
    def __init__(self):
        pass

    def resolve_token(self, token: str, file_dir: str, connector_name: str, **kwargs) -> Tuple[str, list]:
        # token format: < artifact name >
        routine: Routine
        if (routine := kwargs.get("routine")) is not None:
            routine.artifacts.append(token)
        return token, []
