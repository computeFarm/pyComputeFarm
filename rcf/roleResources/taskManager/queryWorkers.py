"""
Ask the taskManager for its current list of available workers as well as
platforms.


This "module" MUST be concatinated to the END of the `taskManagerAccess` module.

"""

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

def remainingArgs(queryRequest, optArgsList) :
  pass

async def runQuery(queryRequest) :
  reader, writer = await tcpTMConnection(queryRequest)
  if reader and writer :
    await tcpTMSendRequest(queryRequest, reader, writer)
    result = await tcpTMGetResult(reader, writer)
    await tcpTMCloseConnection(reader, writer)
    print(yaml.dump(result))

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

  asyncio.run(runQuery(queryRequest))

if __name__ == "__main__" :
  sys.exit(runQueryWorkers())

