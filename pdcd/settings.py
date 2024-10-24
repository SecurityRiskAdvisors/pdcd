from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
import os

from .utils import get_user_pdcd_cfg_dir, find_free_local_port


def cfg_file(f: str):
    cfg_env = os.getenv("PDCD_CFGDIR", None)
    cfg_dir: Path
    if cfg_env is None:
        cfg_dir = get_user_pdcd_cfg_dir()
    else:
        cfg_dir = Path(cfg_env)
    cfg_f = cfg_dir / f
    return cfg_f


class GlobalSettings(BaseSettings):
    # general settings
    log_file: str = Field(default=".pdcd.log", env="PDCD_LOGFILE")
    connectors_file: Path = Field(default_factory=lambda: cfg_file("connectors"), env="PDCD_CONNECTORS")

    # docker settings
    docker_mem_limit: str = Field(default="2G", env="PDCD_DOCKER_MEM_LIMIT")
    docker_memswap_limit: str = Field(default="2G", env="PDCD_DOCKER_MEMSWAP_LIMIT")

    # mythic connector settings
    mythic_callback_interval: int = Field(default=15, env="PDCD_MYTHIC_INTERVAL")
    mythic_jitter_percent: int = Field(default=30, env="PDCD_MYTHIC_JITTER")
    mythic_http_geturi: str = Field(default="search", env="PDCD_MYTHIC_HTTP_GETURI")
    mythic_http_posturi: str = Field(default="form", env="PDCD_MYTHIC_HTTP_POSTURI")
    mythic_http_queryuri: str = Field(default="query", env="PDCD_MYTHIC_HTTP_QUERYURI")
    mythic_http_useragent: str = Field(
        default="Mozilla/5.0 (Windows NT 6.3; Trident/7.0; rv:11.0) like Gecko", env="PDCD_MYTHIC_HTTP_UA"
    )
    mythic_smb_pipename: str = Field(default="TSVNCache-00000000487ca41a", env="PDCD_MYTHIC_SMB_PIPENAME")

    # remote connector settings
    smb_share_name: str = Field(default="pdcd", env="PDCD_SMB_SHARE")
    docker_target_port: int = Field(default=2375, env="PDCD_DOCKER_TARGET")
    docker_bind_port: int = Field(default_factory=find_free_local_port, env="PDCD_DOCKER_BIND")
    smb_target_port: int = Field(default=445, env="PDCD_SMB_TARGET")
    smb_bind_port: int = Field(default_factory=find_free_local_port, env="PDCD_SMB_BIND")
    shell_logging: bool = Field(default=True, env="PDCD_SHELL_LOGGING")


global_settings = GlobalSettings()
