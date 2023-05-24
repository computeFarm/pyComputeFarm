"""
Request a new task and then echo the results as they come back...

To keep this script as self contained as possible, we use a fairly simple
command line argument parser (consisting of `checkNextArg`, `popArg`,
`popIntArg`, `setArg`, and `setEnv`)
"""
import asyncio
import json
import sys
import yaml

taskRequest = {
  'progName' : "",
  'host'     : "127.0.0.1",
  'port'     : 8888,
  'type'     : "taskRequest",
  'taskName' : "unknown",
  'taskType' : "unknown",
  'cmd'      : [],
  'env'      : {},
  'dir'      : '',
  'timeOut'  : 100,
  'logPath'  : 'stdout',
#  'mmh3'     : [],
  'verbose'  : False
}

optArgsList = []

def usage() :
  '''
usage: newTask [options] -- taskName workerType [cmdWord ...]

Request a new Task from the TaskManager

positional arguments:

  taskName                A dot seperated "Name" used by
                          cutelogActions to categorize
                          any log information comming from
                          this task
  workerType              Worker type
  cmdWord                 Command for the worker to do

options:
'''
  print(usage.__doc__)

  optHelp = {}
  optKeyLen = 0
  for anOptArg in optArgsList :
    hKeys = ", ".join(anOptArg['key'])
    if optKeyLen < len(hKeys) : optKeyLen = len(hKeys)
    optHelp[hKeys] = anOptArg['msg']
  for anOptKey in sorted(optHelp.keys()) :
    print(f"  {anOptKey.ljust(optKeyLen)} {optHelp[anOptKey]}")
  sys.exit(1)

def setArg(aKey, aValue) :
  """
  Set the taskRequest's key `aKey` to the value `aValue.
  """
  taskRequest[aKey] = aValue

def checkNextArg(aKey) :
  """
  Check the next argument for an optional argument for the currently parsed key
  `aKey`.
  """
  if len(sys.argv) < 1 or sys.argv[0].startswith('-') :
    print(f"Missing optional argument for [{aKey}]")
    usage()

def popArg(aKey) :
  """
  Check the next argument for the value associated with the key `aKey`. If found
  set the taskRequest key `aKey` with the value `aValue`.
  """
  checkNextArg(aKey)
  setArg(aKey, sys.argv.pop(0))

def popIntArg(aKey) :
  """
  Pop the next argument (using `popArg`) but ensure the taskRequest's value is a
  integer.
  """
  popArg(aKey)
  taskRequest[aKey] = int(taskRequest[aKey])

#def addMmh3() :
#  checkNextArg('mmh3')
#  taskRequest['mmh3'].append(sys.argv.pop(0))

def setEnv() :
  """
  Pop the next argument checking to see if it is a an environment setting
  (contains an `=` with no spaces).

  If it is an enironment setting, add it to the taskRequest's `env` key.
  """
  anEnvTuple = sys.argv.pop(0).split('=')
  if len(anEnvTuple) != 2 :
    print("Environment variable arguments MUST be of the form:")
    print("  NAME=value")
    usage()
  taskRequest['env'][anEnvTuple[0]] = anEnvTuple[1]

optArgsList.append({
    'key' : [ '--help' ],
    'msg' : "Show this help message and exit",
    'fnc' : usage
  })
optArgsList.append({
    'key' : [ '-h', '--host' ],
    'msg' : "TaskManager's host",
    'fnc' : lambda : popArg('host')
  })
optArgsList.append({
    'key' : [ '-p', '--port' ],
    'msg' : "TaskManager's port",
    'fnc' : lambda : popIntArg('port')
  })
optArgsList.append({
    'key' : [ '-e', '--env' ],
    'msg' : "Add a task environment variable",
    'fnc' : setEnv
  })
optArgsList.append({
    'key' : [ '-d', '--dir' ],
    'msg' : "Task directory",
    'fnc' : lambda : popArg('dir')
  })
optArgsList.append({
    'key' : [ '-t', '-timeout', '--timeOut' ],
    'msg' : "Task time out in seconds",
    'fnc' : lambda : popIntArg('timeOut')
  })
optArgsList.append({
    'key' : [ '-l', '--log' ],
    'msg' : "Path to the log file",
    'fnc' : lambda : popArg('logPath')
  })
optArgsList.append({
    'key' : [ '-v', '--verbose' ],
    'msg' : "Echo the complete task request",
    'fnc' : lambda : setArg('verbose', True)
  })
#optArgsList.append({
#    'key' : [ '-m', '--mmh'],
#    'msg' : "Only run task if mmh3 changed",
#    'fnc' : addMmh3
#  })
#optArgsList.append({
#    'key' : [ ],
#    'msg' : "",
#    'fnc' :
#  })

def runNewTask() :
  """
  Compile a JSON taskRequest structure from the command line arguments and then
  send this taskRequest to the registered taskManager. Then wait for the results
  in semi-real time.
  """

  optArgs = {}
  optArgsHelp = [ "options:" ]

  for anOptArg in optArgsList :
    for aKey in anOptArg['key'] :
      optArgs[aKey] = anOptArg['fnc']

  taskRequest['progName'] = sys.argv.pop(0)
  while 0 < len(sys.argv) and sys.argv[0] != '--' :
    anArg = sys.argv.pop(0)
    if anArg in optArgs :
      optArgs[anArg]()
    else :
      print(f"Not expecting: [{anArg}]")
      usage()
  if 0 < len(sys.argv) : sys.argv.pop(0)
  if len(sys.argv) < 2 :
    print("Missing taskName and workerType")
    usage()
  taskRequest['taskName'] = sys.argv.pop(0)
  taskRequest['taskType'] = sys.argv.pop(0)
  while 0 < len(sys.argv) :
    anArg = sys.argv.pop(0)
    taskRequest['cmd'].append(anArg)

  print(f"Task name: {taskRequest['taskName']}")
  print(f"Task type: {taskRequest['taskType']}")
  if taskRequest['verbose'] :
    print("Task Request:\n---")
    print(yaml.dump(taskRequest))
    print("---")

  workerReturnCode = None
  def setWorkerReturnCode(aCode) :
    global workerReturnCode
    workerReturnCode = int(aCode)
    print(workerReturnCode)

  async def tcpTaskRequest(taskRequest) :
    try :
      reader, writer = await asyncio.open_connection(
        taskRequest['host'],
        taskRequest['port']
      )
    except ConnectionRefusedError :
      print("Could not connect to the taskManager")
      return
    except Exception as err :
      print(f"Exception({err.__class__.__name__}): {str(err)}")
      return

    # send task request

    writer.write(json.dumps(taskRequest).encode())
    await writer.drain()
    writer.write(b"\n")
    await writer.drain()

    # echo any results

    moreToRead = True
    while moreToRead :
      print("Reading...")
      data = await reader.readuntil()
      aLine = data.decode().strip()
      # print(f'Received: [{aLine}]')
      if 'returncode' in aLine :
        workerJson = json.loads(aLine)
        if 'returncode' in workerJson :
          setWorkerReturnCode(workerJson['returncode'])
        if 'msg' in workerJson :
          print(workerJson['msg'])
        moreToRead = False
      if reader.at_eof()       : moreToRead = False

    print("Closing the connection")
    writer.close()
    await writer.wait_closed()

  asyncio.run(tcpTaskRequest(taskRequest))

  if workerReturnCode is None : workerReturnCode = 1
  print(f"Return code: {workerReturnCode}")
  sys.exit(workerReturnCode)

if __name__ == "__main__" :
  sys.exit(runNewTask())