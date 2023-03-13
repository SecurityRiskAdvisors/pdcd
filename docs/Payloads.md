# Payloads

## Special CLI tokens

Payload CLIs can use special tokens to call additional functionality.

Aside from connector-specific token, PDCD supports the following tokens:

- `@files` for calling stored files
- `@artifact` for indicating a file is an artifact


## File registry & token

Artifact values from jobs can be stored by a name for use in other payloads. This removes the need to refer to the artifact by its value directly, making it easier to make changes to the parent job and have those changes propagate to all dependent jobs.

Store artifacts can then be called by the special CLI token using `@files` with the value being the stored artifact name. When a payload uses this token, a dependency on the payload that originally stored the artifact is added.

The main drawback of this function is that it currently is only compatible with single artifact jobs

**Example**

To save the artifact value of `/foo.txt`, use the `store` top-level payload key

```
payloads:
- name: job1
  image: ubuntu
  cli: touch /foo.txt
  artifacts:
  - /foo.txt
  store: foo
```

In another job, call the stored value via the CLI token

```
...
- name: job2
  image: ubuntu
  cli: touch @files::foo
```

This is equivalent to the following configuration

```
payloads:
- name: job1
  image: ubuntu
  cli: touch /foo.txt
  artifacts:
  - /foo.txt
- name: job2
  image: ubuntu
  cli: touch /shared/foo.txt
  dependencies:
  - job1
```

There are several notable differences when using the file registry vs not using it:

- the second job must explicitly add a dependency on the first whereas the registry adds it automatically
- the artifact name in the command line must be provided directly and also must be changed to include the `/shared` directory prefix

## Artifact token

The artifact CLI token indicates to PDCD that the value in the command line is also an artifact. It can be used via the `@artifact` token combined with the target path.

**Example**

```
- name: job1
  image: ubuntu
  cli: touch @artifact::/foo.txt
```

is equivalent to 

```
- name: job1
  image: ubuntu
  cli: touch /foo.txt
  artifacts:
  - /foo.txt
```

## CLI considerations

- Keep in mind that the CLI is provided directly to Docker after all token resolution occurs. This means the command must follow the conventions of the container's operating system and default shell. This can potentially cause issues with redirection/piping. In such cases, considered explicitly calling the desired shell. 
    - For example: use `bash -c 'echo foo > bar.txt'` instead of `echo foo > bar.txt`
- Since CLIs can themselves contain command-lines for nested commands, the tool with perform tokenization twice, once for the standard flow then once again if any tokens contain a space. This is a naive approach meant to address common nesting scenarios (e.g. `bash -c '<nested commands>'`). This effectively means that special CLI tokens should work in both the top level command-line and a nested command line, but not necessarily at any level beyond that.

