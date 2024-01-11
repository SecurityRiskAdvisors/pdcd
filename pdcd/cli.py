import os
import click

from .config import Config
from .routines import Routine
from .jobs import JobHandler

from .log import logger
from .settings import global_settings


def log_settings():
    # log the global settings to the log after resolving environment vars
    logger.info(f"Using global settings: {global_settings.json()}")


def validate_path_exists(path) -> bool:
    if not os.path.exists(path):
        raise click.BadParameter(f'File "{path}" does not exist')
    return path


def handle_config_input(ctx, param, value):
    # callback handler for auto-converting a path input value to a Config object
    validate_path_exists(value)
    cfg = Config.from_file(value)
    log_settings()
    return cfg


class SharedOptions:
    # given a str, validate it exists then transform it to a Config object
    #   note: this will start the port-forwards if the remote connector is present
    config = click.option(
        "-c", "--config", "config", help="path to config file", type=str, required=True, callback=handle_config_input
    )


@click.group()
def main():
    pass


@click.command("run")
@SharedOptions.config
def subcmd_run(config: Config, **kwargs):
    # init'ing the routines will cause the token resolution (therefore downloading shellcode) so its done first
    routines = [Routine(**payload.__dict__, config=config) for payload in config.payloads]

    # after generation, push local files to share
    if config.remote_build:
        config.file_manager.sync_local_to_remote()

    # run all jobs
    jobhandler = JobHandler(routines=routines, workers=config.workers)
    jobhandler.run()

    # pull down all remote files after completion
    if config.remote_build:
        config.file_manager.sync_remote_to_local()

    # cleanup activities
    jobhandler.cleanup_routines()
    config.cleanup_resources()


@click.command("logs")
@SharedOptions.config
@click.option(
    "-l", "--limit", "limit", type=int, help="max number of containers to retrieve from", required=False, default=3
)
@click.option("-i", "--image", "image", type=str, help="limit logs to just this image", required=False)
def subcmd_logs(config: Config, limit: int, image: str = None):
    docker = config.client_manager.get_client_by_name("docker").client

    if image:
        images = [image]
    else:
        images = [payload.image for payload in config.payloads]

    aws_arn = None
    if config.remote_build:
        aws_arn = config.remote_client.fwd_params.aws_arn

    for image in images:
        # the "limit" arg limits the number of containers to pull logs from *per image*
        #   this means if you have multiple jobs using the same id, the limit needs to be
        #   the number of those jobs in order to view all logs for the config
        logs = docker.get_ctr_logs_by_imagename(image=image, aws_arn=aws_arn, list_args={"limit": limit})
        banner = image if not aws_arn else f"{image} (ARN: {aws_arn})"
        click.echo(f"=== Image: {banner} ===\n")
        for short_id, values in logs.items():
            click.echo(f"\t---\n\tID: {short_id}\n\t---")
            click.echo(f"\t{values['logs'].decode()}")


main.add_command(subcmd_run)
main.add_command(subcmd_logs)


if __name__ == "__main__":
    main()
