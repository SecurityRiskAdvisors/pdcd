# Connectors

Connectors provide additional functionality to PDCD by using external services. 
PDCD currently supports the following connectors:

- `cobaltstrike` for pulling artifacts from a Cobalt Strike teamserver
- `mythic` for pulling artifacts from a Mythic teamserver
- `remote` for executing container jobs on a remote EC2 instance

Connectors are supplied in the `connectors` top-level key of the config and use the following format

```
connectors:
  <name>:
    type: <type>
    args:
      <key>: <value>
```

The name is a value used in the CLI to refer to the connector. It can be any hashable value except `docker`, `files`, or `artifact`.
The type is one of the above connector types (e.g. `cobaltstrike`).
The args are specific to the connector type. See below for details.

## CLI tokens

Once configured, connectors can be used in the payload CLI using special format of:

> @<name>::<token>

Where name is the connector name and token is the connector-specific token.

# Connectors details

## Cobalt Strike connector

|Key|Description|Example|
|---|---|---|
|password|password|password|
|host|CS host|1.2.3.4|
|port|CS port|50050|
|install_dir|Directory where CS is located|/opt/cobaltstrike|

If the Cobalt Strike connector is configured, you can use a special command-line token to dynamically include Cobalt Strike shellcode (will be placed in file_dir directory).
The format is:

> <STAGED/STAGELESS>[PS]-<64/86>-<LISTENER>-[B64]

The first part is whether the artifact is staged or stageless. If this part ends with "PS" it will be a PowerShell script rather than raw shellcode.
The second part is the architecture.
The third part is the listener name.
The fourth part is whether the artifact should be base-64 encoded and is optional. Parts 1-3 are required.

Examples ("cobaltstrike" is used to represent the connector name):

x64 stageless shellcode using HTTPS listener: @cobaltstrike::STAGELESS-64-HTTPS

x64 stageless PowerShell using DNS listener: @cobaltstrike::STAGELESSPS-64-DNS

base-64 encoded x86 staged shellcode using HTTPS listener: @cobaltstrike::STAGED-86-HTTPS-B64

*Note:* 

This tool will connect to the teamserver using the following username format

> pdcd_<epoch>_<rand 8-char string>


## Mythic connector

|Key|Description|Example|
|---|---|---|
|user|user|neo|
|password|password|password|
|host|Mythic host|1.2.3.4|
|port|Mythic management port|7443|
|callback_url|redirector url (no ending slash)|https://example.com|
|callback_port|redirector port|443|

The Mythic connector works the same as Cobalt Strike connector.
More specifically, it supports the Apollo payload type using either an HTTP(S) or SMB listener.
The token format is:

> <ARTIFACT>-<PROFILE>

The first part is the artifact type and will be either "SHELLCODE" or "EXE"
The second part is the name of the profile. Typically this will be "HTTP" (even for HTTPS).

Examples ("mythic" is used to represent the connector name):

Exe using HTTPS callback: @mythic::EXE-HTTP

*Note: Mythic stores callback connection configurations on a per-payload basis. This needs to be specified in the connector config and not the CLI token. This includes HTTP vs HTTPS and the port. PDCD will use its own default settings for all other payload settings. These can be overridden via environment variables - see [Settings.md](Settings.md).*

## Remote connector

|Key|Description|Example|
|---|---|---|
|aws_instance_id|ID of AWS EC2 instance|i-abcd|
|aws_region|AWS region where above instance is located|us-east-1|
|aws_profile|AWS credential profile name|default|
|mnt_dir|Path on EC2 instance to mount as "/shared" inside containers|/home/ubuntu/smb|

The remote connector allows you to execute the Docker containers on a remote host. Orchestration is still handled locally on the client. The requirements for the remote mode are:

- AWS EC2 instance
  - AWS SSM is configured for remote access to this instance
  - Docker is installed and the Docker daemon is configured to bind to TCP (loopback is fine)
  - Instance is running an SMB file server
    - Has a share called "pdcd" that allows for guest reading/writing
- User has an AWS credential configured that is authorized to remotely connect to the instance over SSM
- User has the AWS SSM Session Manager plugin installed locally: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html

*Note: Docker/SMB settings (e.g. ports, share name) can be configured via environment variables - see [Settings.md](Settings.md).*

When this connector is configured, PDCD will run in remote mode. This changes the execution flow to the following:

1. Create a local port forward to Docker and SMB on instance
2. Upload local files in file_dir to SMB share
3. Execution runs as normal on remote host
4. Download remote files to file_dir from SMB share

Since container execution is performed remotely, the remote host **must** have the container image in its own image cache, not the user's local image cache. Also keep in mind that you cannot commingle different operating systems images in the same config (e.g. using both Windows and Linux images). This is a Docker limitation.

Docker images created during remote mode will have an additional label created for the user's AWS ARN. This is used for additional filtering for the `log` subcommand to retrieve only containers created by the user.

This connector is compatible with the Cobalt Strike/Mythic connectors. These will run first, resolving all special CLI tokens in the config to local temporary files, then the remote connector will upload those to the SMB share before job execution.

If you would like to use Docker commands directly against the instance, you can do so by first manually creating a port forard like so (9998 is arbitrary)

```
aws ssm start-session --target <instance id> --document-name AWS-StartPortForwardingSession --parameters "portNumber"=["2375"],"localPortNumber"=["9998"]
```

then running your Docker CLI commands like so

```
DOCKER_HOST=tcp://127.0.0.1:9998 docker ...
```

# Shared connectors

Connectors can also be stored outside the config file. 
The default location for this shared connectors file is `~/.pdcd/connectors`. 
However, this can be controlled via either the `PDCD_CFGDIR` (directory) or `PDCD_CONNECTORS` (file path) environment variables.

The format of this document is the same as the `connectors` section of the config.
