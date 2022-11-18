# Things to do....

## Worker

1. Add node info into taskRequest
2. Echo (updated) taskRequest back to taskManager and hence cutelogActions
3. Add node info and worker name to all messages going back to taskManager

## NewTask

1. Add host/port command line arguments

2. Add fast finger printing of files to check if they actually need to be
   rebuilt. See:

   - https://github.com/hajimes/mmh3
   - https://github.com/wc-duck/pymmh3
   - https://pypi.org/project/mmh3/
   - https://pypi.org/project/murmurhash3/
   - https://github.com/aappleby/smhasher
   - https://github.com/ninja-build/ninja/issues/1459

## TaskManager

?

## Readme

1. Add new required variables (taskManager/cutelogActions
   host/interface/port)

## Resources

- https://cryptography.io/en/latest/
- https://www.thepythoncode.com/article/encrypt-decrypt-files-symmetric-python#file-encryption-with-password
- https://github.com/getsenic/senic.cryptoyaml
