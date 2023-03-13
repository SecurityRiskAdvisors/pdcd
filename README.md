# PDC Docker ("PDCD")

PDC Docker is a lightweight tool that orchestrates executing Docker containers.

Documentation can be found in the [docs directory](docs/).

Release blog can be found here: [link](TBD).

## Setup

- Have Python 3 installed
- Have Docker installed
- (Optional) AWS SSM Session Manager Plugin
  - used for remote mode, see below for mode information

### Using virtualenv

```
pip install dist/*.whl
```

## Usage (running)

Execute payloads in config

```
pdcd run -c <config file> [-w <# workers>]
```

- **-c** path to config file

## Usage (logs)

Retrieve logs for payloads in config

*Note:* only usable when cleanup is set to "False" in config

```
pdcd logs -c <config file> [-l <#>] [-i <image>]
```

- **-c** path to config file
- **l** max number of logs to retrieve
- **i** filter to only this specific image
