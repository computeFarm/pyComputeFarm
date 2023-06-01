"""
Provide the logging methods for interaction with the CuteLogActions tool.
"""

cutelogActionsWriter = None

async def openCutelog(cutelogActionsHost, cutelogActionsPort) :
  """
  Open the tcp connection to our cuteLogActions GUI.

  This GUI allows the user to locally monitor the progress of their computation
  as various sub-tasks get computed by the computeFarm.
  """
  global cutelogActionsWriter
  if cutelogActionsHost and cutelogActionsPort :
    for attempt in range(60) :
      try :
        cutelogActionsReader, cutelogActionsWriter = await asyncio.open_connection(
          cutelogActionsHost, int(cutelogActionsPort)
        )
        print(f"Connected to the cutelogActions on the {attempt} attempt")
        sys.stdout.flush()
        break
      except :
        cutelogActionsWriter = None
        print(f"Could not connect to cutelogActions on the {attempt} attempt")
        sys.stdout.flush()
      await asyncio.sleep(1)

async def cutelog(jsonLog) :
  """
  Send a log message to the open cuteLogActions GUI.
  """
  if not cutelogActionsWriter :
    if isinstance(jsonLog, str) :
      print("+++++++++++++++++++++++")
      print(jsonLog)
      print("-----------------------")
    else :
      print(">>>>>>>>>>>>>>>>>>>>>>>")
      print(yaml.dump(jsonLog))
      print("<<<<<<<<<<<<<<<<<<<<<<<")
    print("NO cutelogActionsWriter!")
    sys.stdout.flush()
    return

  if isinstance(jsonLog, dict) :
    jsonLog = json.dumps(jsonLog)

  if isinstance(jsonLog, str) :
    jsonLog = jsonLog.encode()

  cutelogActionsWriter.write(len(jsonLog).to_bytes(4,'big'))
  cutelogActionsWriter.write(jsonLog)
  await cutelogActionsWriter.drain()

async def cutelogLog(level, msg, name=None) :
  """
  Add the time, name and level to the base cuteLog message provided, and then
  send the message (using `cuteLog`) to the cuteLogActions GUI.
  """
  logBody = msg
  if isinstance(msg, str) : logBody = { 'msg' : msg }
  logBody['time'] = time.time()
  if name : logBody['name'] = f'taskManager.{name}'
  else    : logBody['name'] = 'taskManager'
  logBody['level'] = level
  await cutelog(logBody)

async def cutelogInfo(msg, name=None) :
  """
  Send a cuteLog message at the `Info` level.
  """
  await cutelogLog('info', msg, name)

async def cutelogDebug(msg, name=None) :
  """
  Send a cuteLog message at the `Debug` level.
  """
  await cutelogLog('debug', msg, name)
