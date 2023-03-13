import os
import logging

from .settings import global_settings

# suppress AWS SDK logging
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("botocore").setLevel(logging.CRITICAL)

logfile = global_settings.log_file
logging.basicConfig(
    filename=logfile,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(pathname)s | [%(module)s.%(funcName)s:%(lineno)d] %(message)s",
    filemode="w",
)
logger = logging.getLogger("pdcd")


def print_and_log(msg, msg_type="info"):
    fn = getattr(logger, msg_type)
    fn(msg)
    print(msg)
