# General troubleshooting steps

## Logs

Some errors will be bubbled-up into the default log file. Refer to [Logs.md](Logs.md) for more info.

## Container errors

Currently, PDCD does not break if a single job fails. You will however not see its artifacts in the output directory.
If you want to investigate why a job failed, perform the following:

1. Set `cleanup` to `False` in the config
2. Run PDCD
3. Get the failed job's container ID
   1. > docker ps -a 
   2. Look for the job's image name in the output and note the container ID
4. Inspect container logs
   1. > docker logs abcd
   2. replace `abcd` with container id

Alternatively, you can use the builtin `log` subcommand to retrieve logs for all containers of all (or a select) images in the config. `cleanup: False` still required).

If you need to further debug, you can get a shell in a completed job's container by doing the following:

1. Get the container ID via the process above
2. Save the container as an image
   1. > docker commit abcd efgh
   2. replace `abcd` with container id
   3. replace `efgh` with some arbitrary name
3. Start shell in new image
   1. > docker run --rm -it --entrypoint sh efgh
   2. replace `efgh` with value used above
   3. `sh` can be replaced with a different shell if that shell is installed (e.g. `bash`)
4. When you're done
   1. > exit
   2. > docker rmi efgh
      1. will delete the temp image
      2. replace `edfg` with value used above
   3. > docker rm abcd
      1. will delete the exited container
      2. replace `abcd` with value used above
   4. > docker rm $(docker ps -qa --no-trunc --filter "status=exited")
      1. alternatively you can use this command to delete all exited containers
