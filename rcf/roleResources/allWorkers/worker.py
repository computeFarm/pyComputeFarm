"""
 Register for a class of task with the central taskManager and then proceed to
 run that task sending the output back to the taskManager (over the open tcp
 channel).

 Initial interaction with the taskManager is via JSON RPC over a single open tcp
 channel.

"""

import asyncio
import importlib
import json
import os
import platform
import sys
import tempfile
import time
import traceback
import yaml

sys.path.append(os.path.expanduser('~/.local/pyComputeFarm/lib'))

def usage() :
  '''
usage: worker workerName [configFile]

Start up a task worker

optional positional argument:
  workerName  The name of this worker
  configFile  A path to this worker's YAML configuration file
              (default: ./workerConfig.yaml)
options:
  -h, --help   Show this help message and exit
  '''

  print(usage.__doc__)
  sys.exit(1)

def compileActionScript(someAliases, someEnvs, someActions) :
  """
  Create a (unix) shell script which can run the actions specified by the
  `someActions` (list of lists or strings) parameter using (unix shell)
  environment variables specified in the `someEnvs` (list of dicts) parameter as
  well as the aliases specified in the `someAliases` (dict) parameter.
  """

  # consider using os.path.expanduser and our own normalizePath

  actionScript = []
  actionScript.append("#!/bin/sh")

  actionScript.append("# export the aliases...")
  if isinstance(someAliases, dict) :
    for aKey, aValue in someAliases.items() :
      actionScript.append(f"alias {aKey}=\"{aValue}\"")

  actionScript.append("# export the environment...")
  if isinstance(someEnvs, list) :
    for anEnv in someEnvs :
      if isinstance(anEnv, dict) :
        for aKey, aValue in anEnv.items() :
          actionScript.append(f"export {aKey}=\"{aValue}\"")

  actionScript.append("# now run the actions...")
  for anAction in someActions :
    if isinstance(anAction, str) :
      actionScript.append(anAction)
    elif isinstance(anAction, list) :
      actionScript.append(" ".join(anAction))

  return "\n\n".join(actionScript)

def runWorker() :
  """
  Run a single worker by opening a tcp connection to the taskManager, register
  the type of work that this worker is able to perform (as a JSON RPC message),
  and then wait for a return JSON RPC message detailing the task.

  Run the requested task and send back the task command's output/stderr in
  semi-realtime.

  Once the task has been completed, exit and let the systemctl restart a new
  worker.

  ------------------------------------------------------------------------------

  The worker's YAML config file (see usage) contains the following keys:

  - taskManager:
      host:  (the host on which to contact the taskManager)
      
      port:  (the port on which to contact the taskManager)

  - logParser: (the (python) log parser to use to parse the task's command
                output)

  - workerType: (the name/type of this worker)

  - availableTools: (a set of commands which this worker understands/supports)

  - aliases: (a dict of command aliases which can be used in any collection of
              actions)

  - env: (a python dict containing the task command's (key: value) environment)

  - dir: (a path to cd into before running the task's command)

  - verbose: (a boolean which if True ensures the worker's actions are logged as
              well as the task's command output)
  """

  for anArg in sys.argv :
    if anArg == '-h' or anArg == '--help' :
      usage()

  if len(sys.argv) < 3 :
    usage()

  hostName   = platform.node()
  workerName = sys.argv[1]

  configFile = "workerConfig.yaml"
  if 2 < len(sys.argv) :
    configFile = sys.argv[2]

  config = {}
  try :
    with open(configFile) as yamlFile :
      config = yaml.safe_load(yamlFile.read())
  except FileNotFoundError :
    print(f"Could not load the {configFile}")
    sys.exit(1)

  if 'workerType' not in config :
    print("Worker configuration MUST include the worker type!")
    sys.exit(1)

  if 'taskManager' not in config :
    config['taskManager'] = {}
  taskManager = config['taskManager']
  if 'host' not in taskManager :
    taskManager['host'] = 'localhost'
  if 'port' not in taskManager :
    taskManager['port'] = 8888

  def defaultLogParser(taskRequest, logMsg) :
    return {
      'time'  : time.time(),
      'name'  : taskRequest['taskName'],
      'level' : 'debug',
      'msg'   : logMsg
    }

  logParserFunc = None
  if 'logParser' in config :
    try :
      thePlugin = importlib.import_module(config['logParser'])
      if thePlugin and hasattr(thePlugin, 'logParser') :
        print(f"Using logParser loaded from {config['logParser']}")
        logParserFunc = thePlugin.logParser
    except Exception :
      print(f"Could not load logParser from [{config['logParser']}]")
      print(traceback.format_exc())
  if not logParserFunc :
    print("Using the default logParser")
    logParserFunc = defaultLogParser

  if 'availableTools' not in config :
    config['availableTools'] = {}

  if 'env' not in config :
    config['env'] = {}
  if type(config['env']) is not dict :
    print("The env MUST be a dictionary")
    sys.exit(1)

  if 'workerName' not in config :
    config['workerName'] = config['workerType']

  if 'verbose' in config :
    print("Worker configuration:\n---")
    print(yaml.dump(config))
    print("---")

  async def jsonLog(writer, aLogDict) :
    aLogDict['worker'] = workerName
    aLogDict['host']   = hostName
    if 'time'  not in aLogDict : aLogDict['time']  = time.time()
    if 'level' not in aLogDict : aLogDict['level'] = 'debug'
    writer.write(json.dumps(aLogDict).encode())
    writer.write(b'\n')
    await writer.drain()

  async def tcpWorker(config) :
    workerType = config['workerType']
    print(f"Starting [{workerType}] worker")

    for attempt in range(60) :
      try :
        reader, writer = await asyncio.open_connection(
          config['taskManager']['host'],
          int(config['taskManager']['port'])
        )
        print(f"Connected to taskManager on the {attempt} attempt")
        sys.stdout.flush()
        break
      except :
        reader = None
        writer = None
        print(f"Could not connect to taskManager on the {attempt} attempt")
        sys.stdout.flush()
      await asyncio.sleep(1)

    if reader is None or writer is None :
      print(f"Could NOT connect to taskManager after {attempt} attempts")
      sys.stdout.flush()
      sys.exit(1)

    # send task specialty
    print("Sending task description to taskManager")
    writer.write(json.dumps({
      'type'           : 'worker',
      'taskType'       : workerType,
      'host'           : hostName,
      'workerName'     : workerName,
      'availableTools' : config['availableTools']
    }).encode())
    await writer.drain()
    writer.write(b"\n")
    await writer.drain()

    # wait for task request
    print("Waiting for responses...")
    taskRequestJson = await reader.readuntil()
    taskRequest = {}
    if taskRequestJson :
      taskRequest = json.loads(taskRequestJson.decode())

    if 'type' in taskRequest and taskRequest['type'] == 'taskRequest' :
      if 'taskName' not in taskRequest :
        taskRequest['taskName'] = config['workerName']
      if 'verbose' in config :
        print("\nTask request:\n---")
        print(yaml.dump(taskRequest))
        print("---")

      ###################################################################
      # setup process
      taskDir = '.'
      if 'dir' in taskRequest and taskRequest['dir'] :
        taskDir = taskRequest['dir']

      taskEnv = None
      if ('env' in taskRequest and
         taskRequest['env'] and
         type(taskRequest['env']) == dict) :
        taskEnv = taskRequest['env']
        localEnv = dict(os.environ)
        for aKey, aValue in taskEnv.items() :
          localEnv[aKey] = aValue
        taskEnv = localEnv

      #TODO: need to rework this to use compileActionScript
      #TODO: need to combine worker and task environment
      
      taskAliases = {}
      if 'aliases' in taskRequest and isinstance(taskRequest['aliases'], dict) :
        taskAliases = taskRequest['aliases']

      taskActions = []
      if 'actions' in taskRequest and type(taskRequest['actions']) == list :
        taskActions = taskRequest['actions']

      actionScript = compileActionScript(taskAliases, taskEnv, taskActions)
      print("---------------------------------------")
      print(actionScript)
      print("---------------------------------------")
      tmpFile = tempfile.NamedTemporaryFile(prefix='cfdoit-LocalWorkerTask-', delete=False)
      tmpFile.write(actionScript.encode("utf8"))
      tmpFile.close()
      os.chmod(tmpFile.name, 0o755)
      taskCmd = tmpFile.name

      if 'verbose' in config :
        print("subprocess cmd: ")
        print(yaml.dump(taskCmd))
        print("subprocess env:")
        print(yaml.dump(taskEnv))
        print("subprocess dir:")
        print(yaml.dump(taskDir))
        print("current working dir:")
        print(yaml.dump(os.getcwd()))

      try :
        proc = await asyncio.create_subprocess_exec(
          taskCmd,
          stdout=asyncio.subprocess.PIPE,
          stderr=asyncio.subprocess.STDOUT,
          cwd=taskDir,
          env=taskEnv
        )

        ###################################################################
        # echo results
        if 'verbose' in config :
          print("Process stdout/stderr: ")
        procStdOut = proc.stdout
        while not procStdOut.at_eof() :
          aLine = await procStdOut.readline()
          aLine = aLine.decode().strip()
          print(f'Sending: [{aLine}]')
          logMsg = logParserFunc(taskRequest, aLine)
          print(yaml.dump(logMsg))
          await jsonLog(writer, logMsg)
        await proc.wait()
        print(f"Finished task for [{workerType}] returncode = {proc.returncode}")
        msgDict = {
          'name'       : taskRequest['taskName'],
          'msg'        : f"Task competed: {proc.returncode}",
          'returncode' : proc.returncode
        }
        print(yaml.dump(msgDict))
        await jsonLog(writer, msgDict)
      except Exception as err :
        msgDict =  {
          'level'      : 'critical',
          'name'       : taskRequest['taskName'],
          'msg'        : f"Exception({err.__class__.__name__}): {str(err)}",
          'returncode' : 1
        }
        print(yaml.dump(msgDict))
        await jsonLog(writer, msgDict)

    print("Closing the connection")
    writer.close()
    await writer.wait_closed()

  asyncio.run(tcpWorker(config))

if __name__ == "__main__" :
  sys.exit(runWorker())
