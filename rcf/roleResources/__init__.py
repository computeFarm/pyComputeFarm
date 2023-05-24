"""
The collection of currently known workers.

--------------------------------------------------------------------------

Each collection of resources contains a `tasks.yaml` file which describes
the steps required to build, start, stop this type of worker.

The main keys of the `tasks.yaml` files are:

- targetDirs : contains a list of the target directories on the (remote)
               worker which MUST be created before any other files are
               transfered.

- files : contains a list of files to be transfered to the (remote)
          worker. Each file description in the list has a `src`, `dest`,
          and a `mode` key describing what file needs to be transfere,
          where it will go, and what (linux) file mode it will have once
          transfered.

- list : contains a list of files to be transfered (like the `files` key
         above). However each `dest` key can contain an `{aWorker}` string
         format item which will be replaced by the name of the particular
         (sub) worker.

- commands : contains a list of commands that need to be run on the
             (remote) worker before it can be run. Currently this is only
             used by the `taskManager` to compile the `hashCheck.c`
             command line tool.

- start : contains an ordered list of (typically systemctl) commands that
          need to be run to start this (remote) worker.

- stop : contains an ordered list of (typcically systemctl) commands that
         need to be run to stop this (remote) worker.

--------------------------------------------------------------------------

These collection will also typcially contain a collect of additional
Jinja2 template files which when expanded will be pushed to the (remote)
worker, as described in the `files`, and `list` keys contained in the
`tasks.yaml` file.

--------------------------------------------------------------------------

A typical (remote) worker will have:

- systemctl unit files (*.service and *.target) which are used to start
  the actual worker process.

- a YAML configuration file loaded by the worker's `worker` process (see
  the allWorkers package).

- a *-LogParser.py Python module which is loaded by the worker's `worker`
  process (see the allWorkers package). This log parser module provides
  methods to intelligently parse the log output of the worker's command
  set. These parsed log outputs will be forwared back to the taskManager
  and subsequently to the cuteLogActions tool. The cuteLogActions tool is
  used by the user to monitor the ongoing progress (or failure) of the
  computation. In particular, the intelligent parsed log output allows the
  cuteLogAction tool to open the source code being "compiled" to the
  correct location where the logged error was discovered.

--------------------------------------------------------------------------

NOTE: this collection of resources by and large ONLY describes how to
      configure, start and stop a given worker.

      Each worker assumes that its respectivel collection of "commands"
      has already been installed on the given remote computer. (Since most
      of these commands require more sophisticated human involvment in
      their installation)

NOTE: There are notes in the `doc` directory of this project which help
      describe how these more complicated command installation can be
      done.

 """

