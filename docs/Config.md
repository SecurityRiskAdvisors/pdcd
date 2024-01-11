# Config

## Top-level keys

|Key|Description|Example|
|---|---|---|
|file_dir|Directory to mount into job containers (absolute path)|/foo/files/|
|cleanup|Delete job containers after completion. Only needed for debugging|True|
|payloads|List of job configs|see below|
|connectors|List of configs for different external connections|see below|
|workers|Number of jobs to run in parallel (default 2). Keep in mind these are Docker containers, which means they carry some overhead - be conservative when using a non-default value. Also used for SMB upload/download in remote mode.|2|
|settings|Override settings at the config-level (alternative to environment variables)|see below|


## Payload config

|Key|Description|Example|
|---|---|---|
|name|Name of job; only used for dependencies|sharpshooter-js|
|image|Docker image name in local cache|sharpshooter|
|cli|Command-line for the container. This will depend on the entrypoint defined in the dockerfile|--help|
|artifacts|List of files to pull from the job after completion. Files will be placed into the file_dir directory|abc.exe|
|dependencies|List of jobs to run before this one. Only needed when the output of one job is required as input for another|sharpshooter-js|
|store|Store the artifact into a variable for future retrieval by @files CLI token|abc-exe|

**Dependencies**

Jobs without dependencies will be put into a batch that is executed first. 
Then, all jobs with dependencies that have been completed in the previous batch are executed next.
This repeats until all jobs are complete. 
Dependencies cannot be cyclical (e.g. job2 depends on job1 and job1 depends on job2).

## Settings

The `settings` key allows for config-level overrides of settings defined in [Settings.md](Settings.md).
This is an alternative method of providing the settings values to environment variables and will override values specified via environment variables.

The value of `settings` should be a map of key-value pairs where each key is one of the values from the "Config Name" column in [Settings.md](Settings.md).

To check the values of these settings for a run, review the log file after execution completes.

Example for overriding the Mythic GET and POST URIs:

```yaml
settings:
  mythic_http_geturi: test
  mythic_http_posturi: test
```
