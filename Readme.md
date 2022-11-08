# Ansible collection which builds distributed python based Compute Farms

An ansible collection which can be used to build distributed python based
Compute Farms.

## Required configuration

To make use of this project you MUST provide the following missing files
and directories:

1. `hosts` (file)

2. `group_vars` (directory)

3. `host_vars` (directory)

Each of these files and directories contains information about *your*
system and so can not be part of this project.

The `hosts` file must contain sections describing which hosts can run the
following tasks:

- guiServer
- verifastWorker
- contextWorker
- compileX86Worker
- compileArmWorker

The `group_vars` and or `host_vars` directories must contain the following
variables:

- `systemPython` provides the name to be used by `/usr/bin/env` to find
                 the required python interpreter.

- `ssh_key` provides a path relative to the user's $HOME/.ssh directory to
            the key to be added to the local ssh agent.

- `vault_ssh_pass` provides the user's password required to use the
                  `ssh_key` specified above. Typically this password will
                  be found in the `group_vars/all/vautl` file and will
                  encrypted using ansible-vault.

## Usage

To *start* a compute farm type:

```
./tasks/startComputeFarm
```

To *stop* a compute farm type:

```
./tasks/stopComputeFarm
```
