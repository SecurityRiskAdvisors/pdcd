import subprocess
import os
import platform
import socket
import uuid
import pathlib
from contextlib import closing
from enum import Enum


def shell(cli: list, env: dict = None, timeout: int = 60, check: bool = True, **kwargs) -> bytes:
    """
    run shell command

    :param cli: entire command as a list
    :param env: additional environment vars to include
    :param timeout: number of seconds to wait for command; defaults to one minute
    :param kwargs: additional args for subprocess.run
    :param check: check exit code
    :return: stdout+stderr
    """
    new_env = os.environ.copy()
    if env:
        new_env = {**new_env, **env}

    from .log import logger
    from .settings import global_settings

    if global_settings.shell_logging:
        logger.info(f"Executing external command {subprocess.list2cmdline(cli)}")

    proc = subprocess.run(
        args=cli, check=check, env=new_env, timeout=timeout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs
    )
    return proc.stdout


def find_free_local_port() -> int:
    # https://stackoverflow.com/a/45690594
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("localhost", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def generate_uuid() -> str:
    return str(uuid.uuid4())


# https://stackoverflow.com/a/7026293
def pad_list(o: list, value, target_length: int):
    o.extend([value] * (target_length - len(o)))
    return o


def get_system_os() -> str:
    return platform.system().lower()


def get_user_pdcd_cfg_dir() -> pathlib.Path:
    if get_system_os() == "windows":
        home_var = "USERPROFILE"
    else:
        # TODO: XDG default vars?
        home_var = "HOME"
    return pathlib.Path(os.environ[home_var] + "/.pdcd")


def file_is_empty(path: str):
    return pathlib.Path(path).stat().st_size == 0


class CaseInsensitiveEnum(Enum):
    """enum that allows for case-insensitive member lookup by name
    CaseInsensitiveEnum("key") -> CaseInsensitiveEnum.Key
    """

    @classmethod
    def _missing_(cls, value):
        # see: https://docs.python.org/3/library/enum.html#enum.Enum._missing_
        #   note that the lookup here is by name rather than by value
        for member in cls:
            if member.name.lower() == value.lower():
                return member
        raise KeyError(f"{value} is not a valid enum member")
