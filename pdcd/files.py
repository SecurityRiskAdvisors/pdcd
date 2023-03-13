from abc import ABC, abstractmethod
from impacket.smbconnection import SMBConnection, SessionError
from typing import List, TYPE_CHECKING
from dataclasses import dataclass
import pathlib
import warnings
import concurrent.futures

from .log import logger

if TYPE_CHECKING:
    from .config import Config


@dataclass
class FSItem:
    # basic wrapper class for a file/directory
    path: str
    is_directory: bool = False

    def __str__(self):
        return self.path if not self.is_directory else f"{self.path}/"

    @property
    def name(self):
        path = self.path
        if path.endswith("/"):
            path = path[0 : len(path) - 1]
        if "/" in path:
            path = path.split("/")[-1]
        return path


class SMBOperations:
    # impacket seemed better than smbprotocol and pysmb for basic guest file writing
    #   smbprotocol also has some issues with guest
    # biggest downside with impacket so far seems to be that connections are very short lived
    #
    # migth wanna come back and make a context handler wrapper for the smbconnection class
    #
    # TODO: some way to cleanup repeated conn+login+close stuff + similar method signatures
    # TODO: look into replacing this with GObject + GIO SMB adapter
    #   downside for this however is that is would be prevent use on Windows hosts (for controller)
    @staticmethod
    def write_file(server: str, port: int, share: str, filename: str, content, directory=None):
        conn = SMBConnection(server, server, "pdcd", port)
        conn.login("", "")
        tree = conn.connectTree(share)
        if directory:
            filename = directory + "\\" + pathlib.Path(filename).name
            try:
                # doesnt look like theres a clean way to create a directory if it already exists without erroring
                # also cant blind delete beforehand
                conn.createDirectory(share, directory)
            except SessionError:
                pass
        smb_file = conn.createFile(tree, filename)
        conn.writeFile(tree, smb_file, content)
        conn.closeFile(tree, smb_file)
        conn.close()

    @staticmethod
    def get_file(server: str, port: int, share: str, src: str, dst: str):
        conn = SMBConnection(server, server, "pdcd", port)
        conn.login("", "")

        with open(dst, "wb") as f:
            conn.getFile(share, src, f.write)

        conn.close()

    @staticmethod
    def list_directory(server: str, port: int, share: str, directory: str = None) -> List[FSItem]:
        conn = SMBConnection(server, server, "pdcd", port)
        conn.login("", "")

        if directory and directory[-1] == "/":  # remove trailing slash
            directory = directory[0 : len(directory) - 1]

        path = "*" if not directory else f"{directory}/*"
        items = conn.listPath(share, path)

        files = []
        for item in items:
            longname = item.get_longname()
            if longname != "." and longname != "..":  # "." and ".." always in results
                if directory:
                    longname = directory + "/" + longname  # directory not included in returned file object
                files.append(FSItem(path=longname, is_directory=item.is_directory() != 0))  # directory = 16, file = 0
        conn.close()
        return files

    @staticmethod
    def delete_file(server: str, port: int, share: str, path: str):
        conn = SMBConnection(server, server, "pdcd", port)
        conn.login("", "")

        conn.deleteFile(share, path)
        conn.close()

    @staticmethod
    def delete_empty_directory(server: str, port: int, share: str, directory: str):
        conn = SMBConnection(server, server, "pdcd", port)
        conn.login("", "")

        conn.deleteDirectory(share, directory)
        conn.close()

    @staticmethod
    def empty_directory(server: str, port: int, share: str, directory: str):
        conn = SMBConnection(server, server, "pdcd", port)
        conn.login("", "")

        dir_files = SMBOperations.list_directory(server, port, share, directory)
        for dir_file in dir_files:
            if dir_file.is_directory:
                SMBOperations.empty_directory(server, port, share, dir_file.path)
                SMBOperations.delete_empty_directory(server, port, share, dir_file.path)
            else:
                SMBOperations.delete_file(server, port, share, dir_file.path)

    @staticmethod
    def delete_directory(server: str, port: int, share: str, directory: str):
        """recursively empties a directory then deletes it"""
        conn = SMBConnection(server, server, "pdcd", port)
        conn.login("", "")

        SMBOperations.empty_directory(server, port, share, directory)
        SMBOperations.delete_empty_directory(server, port, share, directory)
        conn.close()

    @staticmethod
    def create_directory(server: str, port: int, share: str, directory: str):
        """recursively empties a directory then deletes it"""
        conn = SMBConnection(server, server, "pdcd", port)
        conn.login("", "")

        conn.createDirectory(share, directory)
        conn.close()


class LocalOperations:
    @staticmethod
    def write_file(content, filename: str):
        with pathlib.Path(filename).open("wb") as f:
            f.write(content)

    @staticmethod
    def list_files_in_directory(directory: str) -> List[str]:
        return [f.resolve().as_posix() for f in pathlib.Path(directory).glob("**/*") if f.is_file()]


class FileManager(ABC):
    # This class defines the requirements for a file manager object to be used by the config
    # The file manager is meant to support drop-in replacements to make different execution
    #   environments easier to adopt
    def __init__(self, config: "Config"):
        self._config = config

    @abstractmethod
    def write(self, content, filename):
        pass


class SMBFileManager(FileManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _do_smb_op(self, op: str, *args, **kwargs):
        logger.info(
            f"Performing SMB operation {op} using port forward on local port {self._config.remote_client.fwd_params.smb_bind_port}"
        )

        return getattr(SMBOperations, op)(
            server="127.0.0.1",
            port=self._config.remote_client.fwd_params.smb_bind_port,
            share=self._config.remote_client.fwd_params.smb_share_name,
            *args,
            **kwargs,
        )

    def write(self, content, filename: str):
        self._do_smb_op(
            "write_file", filename=filename, directory=self._config.remote_client.fwd_params.smb_uuid, content=content
        )

    def upload(self, filename: str):
        self.write(filename=filename, content=pathlib.Path(filename).read_bytes())

    def dir(self, directory: str = None) -> List[str]:
        files = self._do_smb_op("list_directory", directory=directory)
        return [str(f.path) for f in files]

    def download(self, src: str, dst: str):
        return self._do_smb_op("get_file", src=src, dst=dst)

    def rmdir(self, directory: str):
        return self._do_smb_op(
            "delete_directory",
            directory=directory,
        )

    def ls(self, directory: str = None):
        return self._do_smb_op(
            "list_directory",
            directory=directory,
        )

    def mkdir(self, directory: str):
        return self._do_smb_op(
            "create_directory",
            directory=directory,
        )

    def sync_local_to_remote(self):
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=self._config.workers)
        for local_file in LocalOperations.list_files_in_directory(self._config.file_dir):
            pool.submit(self.upload, local_file)
        pool.shutdown(wait=True)

    def sync_remote_to_local(self):
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=self._config.workers)
        # quick test of downloading 10 copies of CS stagelss shellcode:
        #   going from 1 worker -> 4 workers cut download time by around 1/2
        #   note: timing isnt 100% accurate as it also includes setting up/tearing down the port forwards,
        #       which sometimes gets delayed
        # full roundtrip test (local->remote then remote->local) had ~45% time decrease for 1->4 workers
        #   ~25% decrease for 1->2 workers
        # sample size: a few runs
        for smb_file in self.ls(self._config.remote_client.fwd_params.smb_uuid):  # type: FSItem
            if not smb_file.is_directory:
                pool.submit(self.download, src=smb_file.path, dst=f"{self._config.file_dir}/{smb_file.name}")
            else:
                warnings.warn(f'remote directory downloading not yet supported (directory="{smb_file.path}")')
        pool.shutdown(wait=True)


class LocalFileManager(FileManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write(self, content, filename: str):
        file_path = self._config.file_dir + "/" + filename
        LocalOperations.write_file(content, file_path)


def set_fm_for_config(config: "Config"):
    # TODO: this will need to be changed when additional file managers are added
    if config.remote_build:
        fm = SMBFileManager
    else:
        fm = LocalFileManager
    config.file_manager = fm(config)
