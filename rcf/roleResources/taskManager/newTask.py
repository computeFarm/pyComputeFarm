"""
Request a new task and then echo the results as they come back...

To keep this script as self contained as possible, we use a fairly simple
command line argument parser (consisting of `checkNextArg`, `popArg`,
`popIntArg`, `setArg`, and `setEnv`)

This "module" MUST be concatinated to the END of the `taskManagerAccess` module.
"""

def usage(optArgsList) :
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

taskRequest = {
  'progName' : "",
  'host'     : "127.0.0.1",
  'port'     : 8888,
  'type'     : "taskRequest",
  'taskName' : "unknown",
  'taskType' : "unknown",
  'actions'  : [],
  'env'      : {},
  'dir'      : '',
  'timeOut'  : 100,
  'logPath'  : 'stdout',
#  'mmh3'     : [],
  'verbose'  : False
}

optArgsList = []

optArgsList.append({
  'key' : [ '--help' ],
  'msg' : "Show this help message and exit",
  'fnc' : lambda : usage(optArgsList)
})
optArgsList.append({
  'key' : [ '-h', '--host' ],
  'msg' : "TaskManager's host",
  'fnc' : lambda : popArg('host', taskRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-p', '--port' ],
  'msg' : "TaskManager's port",
  'fnc' : lambda : popIntArg('port', taskRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-e', '--env' ],
  'msg' : "Add a task environment variable",
  'fnc' : lambda : setEnv(taskRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-P', '--platform' ],
  'msg' : "The required platform-cpu",
  'fnc' : lambda : popArg('requiredPlatform', taskRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-d', '--dir' ],
  'msg' : "Task directory",
  'fnc' : lambda : popArg('dir', taskRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-t', '-timeout', '--timeOut' ],
  'msg' : "Task time out in seconds",
  'fnc' : lambda : popIntArg('timeOut', taskRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-l', '--log' ],
  'msg' : "Path to the log file",
  'fnc' : lambda : popArg('logPath', taskRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-v', '--verbose' ],
  'msg' : "Echo the complete task request",
  'fnc' : lambda : setArg('verbose', True, taskRequest, optArgsList)
})
#optArgsList.append({
#  'key' : [ '-m', '--mmh'],
#  'msg' : "Only run task if mmh3 changed",
#  'fnc' : addMmh3
#})
#optArgsList.append({
#  'key' : [ ],
#  'msg' : "",
#  'fnc' :
#})

def remainingArgs(requestDict, optArgsList) :
  if len(sys.argv) < 2 :
    print("Missing taskName and workerType")
    usage(optArgsList)
  requestDict['taskName'] = sys.argv.pop(0)
  requestDict['taskType'] = sys.argv.pop(0)
  cmdLine = []
  while 0 < len(sys.argv) :
    anArg = sys.argv.pop(0)
    cmdLine.append(anArg)
  requestDict['actions'].append(cmdLine)

def runNewTask() :
  """
  Compile a JSON taskRequest structure from the command line arguments and then
  send this taskRequest to the registered taskManager. Then wait for the results
  in semi-real time.
  """

  parseCli(taskRequest, optArgsList, remainingArgs)

  print(f"Task name: {taskRequest['taskName']}")
  print(f"Task type: {taskRequest['taskType']}")
  taskRequest['workers'] = [ taskRequest['taskType'] ]
  if taskRequest['verbose'] :
    print("Task Request:\n---")
    print(yaml.dump(taskRequest))
    print("---")

  workerReturnCode = []
  def setWorkerReturnCode(aCode) :
    workerReturnCode.append(int(aCode))
    print(yaml.dump(workerReturnCode))

  tmSocket = tcpTMConnection(taskRequest)
  if tmSocket :
    if tcpTMSentRequest(taskRequest, tmSocket) :
      tcpTMEchoResults(tmSocket, setWorkerReturnCode)  

  if not workerReturnCode : workerReturnCode.append(1)
  print(f"Return code: {workerReturnCode[0]}")
  return workerReturnCode[0]

if __name__ == "__main__" :
  sys.exit(runNewTask())