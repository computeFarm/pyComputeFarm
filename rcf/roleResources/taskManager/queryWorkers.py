"""
Ask the taskManager for its current list of available workers as well as
platforms.


This "module" MUST be concatinated to the END of the `taskManagerAccess` module.

"""

import os
import time

def usage(optArgsList) :
  '''
usage: queryWorkers [options]

Ask the TaskManager for its current list of available workers and platforms

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

queryRequest = {
  'progName' : "",
  'host'     : "127.0.0.1",
  'port'     : 8888,
  'type'     : "workerQuery",
  'taskName' : "workerQuery",
  'taskType' : "workerQuery",
  'verbose'  : False,
  'interval' : 0,
  'raw'      : False
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
  'fnc' : lambda : popArg('host', queryRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-p', '--port' ],
  'msg' : "TaskManager's port",
  'fnc' : lambda : popIntArg('port', queryRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-v', '--verbose' ],
  'msg' : "Echo the complete task request",
  'fnc' : lambda : setArg('verbose', True, queryRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-i', '--interval' ],
  'msg' : "Interval between information refresh (default 0 == no refresh)",
  'fnc' : lambda : popIntArg('interval', queryRequest, optArgsList)
})
optArgsList.append({
  'key' : [ '-r', '--raw' ],
  'msg' : "Print the *raw* information structure",
  'fnc' : lambda : setArg('raw', True, queryRequest, optArgsList)
})

def remainingArgs(queryRequest, optArgsList) :
  pass

def getPrintRequest(queryRequest) :
  verbose = False
  if 'verbose' in queryRequest : verbose = queryRequest['verbose']
  tmSocket = tcpTMConnection(queryRequest, verbose)
  if tmSocket :
    if tcpTMSentRequest(queryRequest, tmSocket, verbose) :
      result = tcpTMGetResult(tmSocket, verbose)
      tcpTMCloseConnection(tmSocket, verbose)
      if queryRequest['raw'] :
        print(yaml.dump(result))
      else :
        print("\nHost information:\n")
        #for aHost, someHostData in result['hostData'].items() :
        print(yaml.dump(result['hostData']))

        print("\nAssigned tasks:\n")
        if result['assignedTasks'] : 
          print(yaml.dump(result['assignedTasks']))
        else :
          print("  no assigned tasks at the moment")

def clearConsole():
  # see: https://stackoverflow.com/questions/71164090/how-to-refresh-overwrite-console-output-in-python
  command = 'clear'
  if os.name in ('nt', 'dos'):  # If computer is running windows use cls
    command = 'cls'
  os.system(command)

def runQueryWorkers() :
  """
  Compile a JSON queryRequest structure from the command line arguments and then
  send this queryRequest to the registered taskManager. Then wait for the results
  in semi-real time.
  """

  parseCli(queryRequest, optArgsList, remainingArgs)

  if queryRequest['verbose'] :
    print("Query Request:\n---")
    print(yaml.dump(queryRequest))
    print("---")

  try :
    if queryRequest['interval'] < 1 :
      getPrintRequest(queryRequest)
    else :
      while 0 < queryRequest['interval'] :
        clearConsole()
        getPrintRequest(queryRequest)
        time.sleep(queryRequest['interval'])
  except KeyboardInterrupt :
    pass
  
  print("")

if __name__ == "__main__" :
  sys.exit(runQueryWorkers())

