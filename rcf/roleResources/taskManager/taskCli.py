"""
To keep the `newTask` and `queryWorkers` tools as self contained as possible, we
use a fairly simple command line argument parser (consisting of `checkNextArg`,
`popArg`, `popIntArg`, `setArg`, and `setEnv`).

This "cli" uses command line arguments to build up / alter a task dict which is
eventualy sent to the taskManager.

This "module" MUST be concatinated BETWEEN the `taskManagerAccess.py` and the
respective `newTask.py` or `queryWorkers.py` "modules".

"""

def setArg(aKey, aValue, requestDict, optArgsList) :
  """
  Set the requestDict's key `aKey` to the value `aValue.
  """
  requestDict[aKey] = aValue

def checkNextArg(aKey, requestDict, optArgsList) :
  """
  Check the next argument for an optional argument for the currently parsed key
  `aKey`.
  """
  if len(sys.argv) < 1 or sys.argv[0].startswith('-') :
    print(f"Missing optional argument for [{aKey}]")
    usage(optArgsList)

def popArg(aKey, requestDict, optArgsList) :
  """
  Check the next argument for the value associated with the key `aKey`. If found
  set the taskRequest key `aKey` with the value `aValue`.
  """
  checkNextArg(aKey, optArgsList)
  setArg(aKey, sys.argv.pop(0), requestDict)

def popIntArg(aKey, requestDict, optArgsList) :
  """
  Pop the next argument (using `popArg`) but ensure the taskRequest's value is a
  integer.
  """
  popArg(aKey, requestDict, optArgsList)
  requestDict[aKey] = int(requestDict[aKey])

#def addMmh3(requestDict, optArgsList) :
#  checkNextArg('mmh3', optArgsList)
#  requestDict['mmh3'].append(sys.argv.pop(0))

def setEnv(requestDict, optArgsList) :
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
  requestDict['env'][anEnvTuple[0]] = anEnvTuple[1]

def parseCli(requestDict, optArgsList, remainingArgs) :

  optArgs = {}
  optArgsHelp = [ "options:" ]

  for anOptArg in optArgsList :
    for aKey in anOptArg['key'] :
      optArgs[aKey] = anOptArg['fnc']

  requestDict['progName'] = sys.argv.pop(0)
  while 0 < len(sys.argv) and sys.argv[0] != '--' :
    anArg = sys.argv.pop(0)
    if anArg in optArgs :
      optArgs[anArg]()
    else :
      print(f"Not expecting: [{anArg}]")
      usage(optArgsList)
  if 0 < len(sys.argv) : sys.argv.pop(0)
  remainingArgs(requestDict, optArgsList)
