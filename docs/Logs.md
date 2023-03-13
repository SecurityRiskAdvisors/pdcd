# Logging

PDCD logs key functionality during execution. 
By default, the log file is `.pdcd.log` (the directory where the tool was executed).
This can be changed via the `PDCD_LOGFILE` environment variable.
Logging external commands run through `utils.shell()` can be suppressed via `PDCD_SHELL_LOGGING` (set to false).

## Log format

Logged events use the format: 

`< time > | < log level > | < file > | [< function >:< line no >] < message >`

- The file is the file path of the code responsible for logging the message
- The function and line number are the location in the file that is responsible for logging the message
- The log level indicates the severity of the event, such as information or error

## Sensitive information

All commands executed through the `utils.shell()` are logged to the logfile. If a command contains sensitive information, that information will be present in the log file. For connectors that rely on integration via an external command(s), those details will be logged. For the Cobalt Strike connector, this includes the password supplied to `agscript`. Use `PDCD_SHELL_LOGGING` to suppress these logs if needed.
