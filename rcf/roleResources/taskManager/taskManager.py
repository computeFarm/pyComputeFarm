"""
Manage a collection of specialized task workers by assigning new tasks
in a simple round-robin fashion using one asyncio Queue for each
specialized task.

Echoing the results from the assigned worker back to the requester.

"""

import asyncio
import json
import signal
import sys
import time
import traceback
import yaml

def usage() :
  '''
usage: taskManager [configFile]

optional positional argument:
  configFile A path to this taskManager's YAML configuration file
             (default: ./taskManager.yaml)

options:
  -h, --help Show this help message and exit
  '''

  print(usage.__doc__)
  sys.exit(0)


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

workerQueues = {}
workerTypes  = {}
hostLoads    = {}
hostTypes    = {}

async def handleConnection(reader, writer) :
  """
  Handle one connection ...

  There are three types of JSON task messages:

  - monitor load information

  - worker registration

  - worker query

  - new task request

  The JSON messages consists of:

  - taskType  (used by both worker registration and new task requests to choose
               the correct worker sub-queue)

  - type      (one of `monitor`, `worker`, `workerQuery`, `taskRequest`)
  
  - host      (monitor messages, the name of the monitored machine)

  - platform  (initial monitor message, the type of OS being monitored
               (`platform.system().lower()`)) 
  
  - cpuType   (initial monitor message, the type of CPU being monitored
               (`platform.machine().lower()`))
  
  - wlOne     (monitor messages stream, work load average over last minute)
  - wlFive    (monitor messages stream, work load average over last five
               minutes)
  - wlFifteen (monitor messages stream, work load average over last fifteen
               minutes)
  
  - numCpus   (monitor messages stream, number of cpu/cores)
  
  - scale     (monitor messages stream, a scale factor configured for this
               machine)

  - taskName  (taskRequest messages, the name of the requested task for use by
               the cuteLogActions GUI)

  - cmd       (taskRequest messages, a list of strings which when joined
               provides the full command)
  
  - env       (taskRequest messages, a dict of key-value pairs which provides
               the command's environment)

  - dir       (taskRequest messages, the directory in which to run the requested
               command)

  For each JSON task message, both the `taskType` and `type` keys MUST exist.

  For each JSON task message recieved, we deal with the simpler (short lived)
  task messages in the following order:

  1. Monitor messages (we simply record the load average information provided
     for that machine and then close this connection).
  
  2. Worker registration (we simply add this this worker/connection to the queue
     of existing workers for later use).

  3. Worker query (return a dict summary of the available workers. The
     `workerTypes` key is a copy of the `workerTypes` global variable. The
     `hostTypes` is a copy of the `platform` and `cpu` keys in the `hostTypes`
     global.)

  4. New task request (we find an existing worker/connection which matches the
     requested task, forward the task request onto the worker, and then echo the
     resulting "stream" of "log" messages back to both the task originator as
     well as the cuteLogActions GUI. When the worker finishes, we close this
     connection)

  ------------------------------------------------------------------------------

  The task manager, maintains four globals, `workerQueues`, `workerTypes`,
  `hostLoads` and `hostTypes`.

  - `workerQueues` : is a dict of dicts indexed by `workerType`s and
                     `workerHost`s. Each entry is a worker waiting for an
                     appropriate task.

  - `workerTypes` : is a dict indexed by `workerType`. Each entry is a list of
                    the tools supported by this `workerType`.

  - `hostLoads` : is a dict indexed by `workerHost`. Each entry contains the
                  latest scaled load average for use when choosing the next
                  worker to be given a task.

  - `hostTypes` : is a dict of dict indexed by `workerPlatform` and `workerCPU`.
                  Each entry contains a set of known hosts of the appropriate
                  platform and cpu type.
  """
  addr = writer.get_extra_info('peername')
  await cutelogDebug(f"Handling new connection from {addr!r}")

  # read task type
  taskJson = await reader.readuntil()
  task = {}
  if taskJson :
    task = json.loads(taskJson.decode())

  taskType = None
  if 'taskType' in task :
    taskType = task['taskType']

  # ensure we have a usable taskType
  if not taskType :
    cutelogDebug("Incorrect task request: missing taskType")
    writer.write("Incorrect task request: missing taskType".encode())
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    return

  # IF task is a monitor... start recording workloads for this host
  if 'type' in task and task['type'] == 'monitor' :
    if 'host' not in task or 'platform' not in task or 'cpuType' not in task :
      await cutelogDebug(f"new monitor without a host, platform, or cpuType... dropping the connection...")
      await cutelogDebug(task)
      writer.close()
      await writer.wait_close()
      return

    monitoredHost = task['host']
    mPlatform     = task['platform']
    mCpuType      = task['cpuType']
    if mPlatform not in hostTypes            : hostTypes[mPlatform] = {}
    if mCpuType  not in hostTypes[mPlatform] : hostTypes[mPlatform][mCpuType] = {}
    if monitoredHost not in hostTypes[mPlatform][mCpuType] :
      hostTypes[mPlatform][mCpuType][monitoredHost] = True
    await cutelogDebug(f"Got a new monitor connection from {monitoredHost}...")
    while not reader.at_eof() :
      try :
        data = await reader.readline()
      except :
        await cutelogDebug(f"{task['host']} monitor close connection...")
        break
      message = data.decode()
      jsonData = json.loads(message)
      scaled   = jsonData['wlOne']/(jsonData['numCpus']*jsonData['scale'])
      jsonData['name']   = 'monitor'
      jsonData['level']  = 'debug'
      jsonData['scaled'] = scaled
      await cutelog(jsonData)
      hostLoads[monitoredHost] = scaled

    # clean up the hostTypes and hostLoads global variables by removing this
    # monitored host
    if mPlatform in hostTypes :
      if mCpuType in hostTypes[mPlatform] :
        if monitoredHost in hostTypes[mPlatform][mCpuType] :
          del hostTypes[mPlatform][mCpuType][monitoredHost]
          if not hostTypes[mPlatform][mCpuType] :
            del hostTypes[mPlatform][mCpuType]
            if not hostTypes[mPlatform] :
              del hostTypes[mPlatform]

    if monitoredHost in hostLoads :
      del hostLoads[monitoredHost]

    cutelogDebug(f"Closing monitor connection ...")
    writer.close()
    await writer.wait_closed()
    return

  # ELSE IF task is a worker... place the reader/writer in a worker queue
  if 'type' in task and task['type'] == 'worker' :
    if 'host' not in task :
      await cutelogDebug(f"new worker without a host... dropping the connection...")
      await cutelogDebug(task)
      writer.close()
      await writer.wait_close()
      return
    workerHost = task['host']

    await cutelogDebug(f"Got a new worker connection...", name=taskType)
    await cutelogDebug(task, name=taskType)
    if taskType not in workerQueues :
      workerQueues[taskType] = {}
    if taskType not in workerTypes :
      workerTypes[taskType] = {}
    if 'availableTools' in task :
      for aTool in task['availableTools'] :
        workerTypes[taskType][aTool] = True
    if workerHost not in workerQueues[taskType] :
      if workerHost not in hostLoads : hostLoads[workerHost] = 1000
      workerQueues[taskType][workerHost] = asyncio.Queue()
    await cutelogDebug(f"Queing {taskType!r} worker on {workerHost}")
    await workerQueues[taskType][workerHost].put({
      'taskType' : taskType,
      'addr'     : addr,
      'reader'   : reader,
      'writer'   : writer
    })
    await cutelogDebug("Waiting for a new connection...")
    return

  # ELSE IF task is a query about types of workers... check the worker queue
  if 'type' in task and task['type'] == 'workerQuery' :
    await cutelogDebug(f"Got a worker query connection...", name='query')

    # collect the host type information (platform, cpuType)
    lHostTypes = {}
    for platformKey, platformValue in hostTypes.items() :
      for cpuKey, cpuValue in platformValue.items() :
        if cpuValue :
          if platformKey not in lHostTypes :
            lHostTypes[platformKey]         = {}
          if cpuKey      not in lHostTypes[platformKey] : 
            lHostTypes[platformKey][cpuKey] = True

    # collect information about the current available workers and tools
    lWorkers = {}
    lTools   = {}
    for workerType in workerQueues :
      if workerType not in lWorkers : lWorkers[workerType] = True
      if workerType in workerTypes :
        for aTool in workerTypes[workerType].keys() :
          if aTool not in lTools : lTools[aTool] = {}
          if workerType not in lTools[aTool] :
            lTools[aTool][workerType] = True
      
    # send worker information 
    print("Sending worker information to queryWorkers/cfdoit")
    writer.write(json.dumps({
      'type'      : 'workerQuery',
      'taskType'  : 'workerQuery',
      'hostTypes' : lHostTypes,
      'workers'   : lWorkers,
      'tools'     : lTools
    }).encode())
    await writer.drain()
    writer.write(b"\n")
    await writer.drain()

    await cutelogDebug("Waiting for a new connection...")
    return

  # ELSE task is a request... get a worker and echo the results
  if taskType not in workerQueues or len(workerQueues[taskType]) < 1 :
    await cutelogDebug(f"No specialist worker found for the task type: [{taskType}]")
    writer.write(
      f"No specialist worker found for the task type: [{taskType}]".encode()
    )
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    return

  while True :
    workerHosts = list(workerQueues[taskType].keys())
    leastLoadedHost = workerHosts.pop(0)
    for aHost in workerHosts :
      if hostLoads[aHost] < hostLoads[leastLoadedHost] :
        leastLoadedHost = aHost
    taskWorker = await workerQueues[taskType][leastLoadedHost].get()
    workerQueues[taskType][leastLoadedHost].task_done()

    try :
      workerAddr   = taskWorker['addr']
      workerReader = taskWorker['reader']
      workerWriter = taskWorker['writer']

      # Send this worker our task request
      workerWriter.write(taskJson)
      await workerWriter.drain()
      workerWriter.write(b"\n")
      await workerWriter.drain()
    except ConnectionResetError :
      await cutelogDebug("The assigned worker has died.... so we are trying the next")
      continue
    # We have found a live worker...
    break

  # add a small fudge factor to the leastLoadedHost's current load to
  # ensure we don't keep choosing and hence over load it
  #
  hostLoads[leastLoadedHost] += 0.1

  while not workerReader.at_eof() :
    try :
      data = await workerReader.readuntil()
    except :
      await cutelogDebug(f"Worker {workerAddr!r} closed connection", name=taskType)
      break

    message = data.decode()
    await cutelogDebug(f"Received [{message!r}] from {workerAddr!r}", name=taskType)
    await cutelogDebug(f"Echoing: [{message!r}] to {addr!r}", name=taskType)
    await cutelog(message)
    if 'returncode' in message :
      writer.write(data)
      #writer.write(b"\n")
      await writer.drain()

  await cutelogDebug(f"Closing the connection to {addr!r}")
  writer.close()
  await writer.wait_closed()

async def tcpTaskServer(config) :
  """
  Run the tcpTaskServer by listening for new connections on the (configured)
  "well known" port.

  To do this we:
  
  - Open the connection to the cuteLogActions GUI.

  - Set up signal handling (to gracefully deal with the SIGHUP, SIGTERM, and
    SIGINT signals) 

  - Start the asynchronous tcp server using the `handleConnection` method to
    handle new connections.

  We then serve forever (or until a singal is caught).
  """
  cutelogActionsHost = config['cutelogActions']['host']
  cutelogActionsPort = config['cutelogActions']['port']

  await openCutelog(cutelogActionsHost, cutelogActionsPort)

  if not cutelogActionsWriter :
    print(f"Could not open connection to cutelogActions at ({cutelogActionsHost}, {cutelogActionsPort}) ")

  loop = asyncio.get_event_loop()

  def signalHandler(signame) :
    print("")
    print(f"SignalHandler: caught signal {signame}")
    if cutelogActionsWriter :
      print("Closing connection to cutelogActions")
      cutelogActionsWriter.close()
    print("Sutting down")
    loop.stop()

  signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
  for s in signals:
    loop.add_signal_handler(s, signalHandler, s.name)

  taskManager = config['taskManager']
  server = await asyncio.start_server(
    handleConnection, taskManager['interface'], taskManager['port']
  )

  addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
  print(f"TaskManager serving on {addrs}")
  await cutelogInfo(f"TaskManager serving on {addrs}")

  async with server :
    await server.serve_forever()

def runTaskManager() :
  """
  Provide a centarl task manager for a compute farm by listening for JSON RPC
  messages on a well known port.

 
  """

  for anArg in sys.argv :
    if anArg == '-h' or anArg == '--help' :
      usage()

  configFile = "taskManager.yaml"
  if 1 < len(sys.argv) :
    configFile = sys.argv[1]

  config = {}
  try :
    with open(configFile) as yamlFile :
      config = yaml.safe_load(yamlFile.read())
  except FileNotFoundError :
    print(f"Could not load the {configFile}")
    sys.exit(1)

  if 'taskManager' not in config :
    config['taskManager'] = {}
  taskManager = config['taskManager']
  if 'interface' not in taskManager :
    taskManager['interface'] = "0.0.0.0"
  if 'port' not in taskManager :
    taskManager['port'] = 8888

  if 'cutelogActions' in config :
    cutelogActions = config['cutelogActions']
    if 'host' not in cutelogActions :
      cutelogActions['host'] = "localhost"
    if 'port' not in cutelogActions :
      cutelogActions['port'] = 19996

  try :
    asyncio.run(tcpTaskServer(config))
  except :
    #pass
    print("Caught and ignored exception")
    print(traceback.format_exc())

if __name__ == "__main__" :
  sys.exit(runTaskManager())
