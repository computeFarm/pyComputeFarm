"""
Implement the logic to handle the incomming connections to the taskManager's
tcpTaskServer.

------------------------------------------------------------------------------

  The task manager, maintains four globals, `workerQueues`, `workerTypes`,
  `hostLoads` and `hostTypes`.

  - `workerQueues` : is a dict of dicts indexed by `workerType`s and
                     `workerHost`s. Each entry is a worker waiting for an
                     appropriate task.

  - `workerTypes`  : is a dict indexed by `workerType`. Each entry is a list of
                     the tools supported by this `workerType`.

  - `hostLoads`    : is a dict indexed by `workerHost`. Each entry contains the
                     latest scaled load average for use when choosing the next
                     worker to be given a task.

  - `hostTypes`    : is a dict of dict indexed by `workerPlatform`-`workerCPU`.
                     Each entry contains a set of known hosts of the appropriate
                     platform and cpu type.
"""

workerQueues         = {}
workerTypes          = {}
platformQueues       = {}
hostLoads            = {}
hostTypes            = {}
fileLocations        = {}

async def handleMonitorConnection(task, reader, writer) :
  """
  Handle a connection from a monitor.

  We record the load average information provided for that machine and then
  close the connection.

  The task dict MUST contain the following keys:

  - host      : the name of the monitored machine

  - platform  : (initial message) the type of OS being monitored
                 (`platform.system().lower()`))
  
  - cpuType   : (initial message) the type of CPU being monitored
                 (`platform.machine().lower()`)
  
  - maxLoad   : the maximum load allowed for this machine

  - wlOne     : work load average over last minute
  - wlFive    : work load average over last five minutes (not currently used)
  - wlFifteen : work load average over last fifteen minutes (not currently used)
  
  - numCpus   : number of cpu/cores
  
  - scale     : a scale factor configured for this machine

  """
  if 'host' not in task or 'platform' not in task or 'cpuType' not in task :
    await cutelogDebug(f"new monitor without a host, platform, or cpuType... dropping the connection...")
    await cutelogDebug(task)
    writer.close()
    await writer.wait_close()
    return

  monitoredHost = task['host']
  mPlatform     = task['platform']
  mCpuType      = task['cpuType']
  thePlatform = f"{mPlatform.lower()}-{mCpuType.lower()}"
  maxLoad = 1.0
  if 'maxLoad' in task : maxLoad = task['maxLoad']

  if thePlatform not in hostTypes : hostTypes[thePlatform] = {}
  if thePlatform not in platformQueues : 
    platformQueues[thePlatform] = asyncio.Queue()

  if monitoredHost not in hostTypes[thePlatform] :
    hostTypes[thePlatform][monitoredHost] = maxLoad

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
  if thePlatform in hostTypes :
    if monitoredHost in hostTypes[thePlatform] :
        del hostTypes[thePlatform][monitoredHost]
        if not hostTypes[thePlatform] :
          del hostTypes[thePlatform]

  if monitoredHost in hostLoads :
    del hostLoads[monitoredHost]

  await cutelogDebug(f"Closing monitor connection ...")
  writer.close()
  await writer.wait_closed()

async def handleWorkerConnection(task, addr, reader, writer) :
  """
  Handle a connection from a worker.

  We add this this worker/connection to the queue of existing workers for later
  use.
 
  The task dict MUST contain the following keys:

  - taskType       : used to choose the correct worker sub-queue

  - host           : the name of the worker's machine (use to match with
                     hostLoads)

  - workerName     : (optional) the name of this worker (for logging)

  - availableTools : (optional) a list of the tools that this worker can use

  """
  if 'host' not in task :
    await cutelogDebug(f"new worker without a host... dropping the connection...")
    await cutelogDebug(task)
    writer.close()
    await writer.wait_close()
    return
  workerHost = task['host']

  if 'taskType' not in task :
    await cutelogDebug("new worker without a taskType... dropping the connection")
    await cutelogDebug(task)
    writer.close()
    await writer.wait_closed()
    return

  taskType = task['taskType']

  workerName = taskType
  if 'workerName' in task : workerName = task['workerName']

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
    'taskType'   : taskType,
    'workerName' : workerName,
    'addr'       : addr,
    'reader'     : reader,
    'writer'     : writer
  })

async def handleQueryConnection(task, reader, writer) :
  """
  Handle a workerQuery connection.

  We return a dict summary of the available workers as a JSON dict with the
  following keys:
  
  - files     : is a dict containing the following paths:

                  - dest (the worker's local base path (as served by sshfs))

                  - orig (the taskManagers local base path (to be served by
                          sshfs))

  - tools     : is a dict of "sets" indexed by tools and available workerTypes
                which can use a given tool.

  - workers   : is a "set" of the available workerTypes
  
  - hostTypes : is a dict of "sets" indexed by the `platform`-`cpu` and
                available workerTypes for that `platform`-`cpu` combination.

  The task dict MUST have the following keys:

  (none)

  """
  await cutelogDebug(f"Got a worker query connection...", name='query')

  # collect information about the platformQueues
  lPlatformQueues = {}
  for aPlatform, aQueue in platformQueues.items() :
    lPlatformQueues[aPlatform] = aQueue.empty()

  # collect the host type information (platform, cpuType)
  lHostTypes = {}
  for platformKey, platformValue in hostTypes.items() :
    if platformKey not in lHostTypes : lHostTypes[platformKey] = {}
    for aHost in platformValue.keys() :
      for aWorkerType, someHosts in workerQueues.items() :
        if aHost in someHosts : lHostTypes[platformKey][aWorkerType] = True

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
    'type'                : 'workerQuery',
    'taskType'            : 'workerQuery',
    'hostTypes'           : lHostTypes,
    'hostLoads'           : hostLoads,
    'workers'             : lWorkers,
    'tools'               : lTools,
    'files'               : fileLocations,
    'platformQueuesEmpty' : lPlatformQueues
  }).encode())
  await writer.drain()
  writer.write(b"\n")
  await writer.drain()

async def dispatcher() :
  """
  Manages the dispatch of paused taskRequest handlers contained in the
  platformQueues.
  
  Each paused taskRequest handler is waiting on a event contained in the
  appropriate platformQueue.

  We only dispatch a new taskRequest handler from a given platformQueue when the
  load on at least one host of the given type drops below its assigned maxLoad.
  """
  while True :
    taskFound = False

    if platformQueues :
      shuffledPlatforms = list(platformQueues.keys())
      random.shuffle(shuffledPlatforms)
      await cutelogDebug(
        { 'shuffledPlatforms' : shuffledPlatforms},
        name="dispatcher"
      )
      for aPlatform in shuffledPlatforms :
        aPlatformQueue = platformQueues[aPlatform]
        await cutelogDebug(
          f"checking for taskRequests queued on the {aPlatform} queue",
          name='dispatcher'
        )
        for aHost, aMaxScaledLoad in hostTypes[aPlatform].items() :
          if hostLoads[aHost] < aMaxScaledLoad :
            if not aPlatformQueue.empty() :
              nextTaskEvent = await aPlatformQueue.get()
              aPlatformQueue.task_done()
              if not nextTaskEvent.is_set() :
                nextTaskEvent.set()  # tell this task to start running....
                taskFound = True
                await cutelogDebug(
                  f"found a taskRequest on the {aPlatform} queue",
                  name='dispatcher'
                )
                break  # only start one task per platform durring one scan
    if not taskFound :
      # if no tasks found during last scan pause
      await cutelogDebug(f"sleeping", name="dispatcher")
      await asyncio.sleep(1)

async def handleTaskRequestConnection(task, taskJson, addr, reader, writer) :
  """
  Handle a taskRequest connection.

  We find an existing worker/connection which matches one of the requested
  workers, forward the task request onto the worker, and then echo the resulting
  "stream" of "log" messages back to both the task originator as well as the
  cuteLogActions GUI. When the worker finishes, we close this connection.

  The task dict (and taskJson) MUST have the following keys:

  - taskName         : the name of the requested task for use by the
                       cuteLogActions GUI
  
  - requiredPlatform : (optional) if provided, the type of host (OS-CPU) that
                       MUST be use to run this task.
  
  - workers          : a list of acceptable workers

  - actions          : a list of lists of strings which when joined provides the
                       the commands (to be run one after the other)
  
  - env              : a dict of key-value pairs which provides the command
                       script's environment

  - dir              : the directory in which to run the command script

  - aliases          : a dict of key-value pairs which provides a collection of
                       shell aliases to be used by the actions

  - estimatedLoad    : a (scaled) estimate of the load associated with this
                       task. This is added to the hostLoad of the host assigned
                       to this task (default: 0.5)
  """
  await cutelogDebug({ 'task' : task }, name="debug")

  if 'workers' not in task or len(task['workers']) < 1 :
    await cutelogDebug("new task request without any workers... dropping the connection")
    await cutelogDebug(task)
    writer.close()
    await writer.wait_closed()
    return

  requiredPlatform = None
  if 'requiredPlatform' in task :
    requiredPlatform = task['requiredPlatform']
  if requiredPlatform and requiredPlatform not in hostTypes :
    await cutelogDebug(f"No platform found for the task request... dropping the connection")
    await cutelogDebug(task)
    writer.close()
    await writer.wait_closed()
    return

  thisTaskEvent = asyncio.Event() # starts with the event cleared

  if requiredPlatform :
    await cutelogDebug(f"stored task event on {requiredPlatform} queue", name="dispatcher")
    await platformQueues[requiredPlatform].put(thisTaskEvent)
  else :
    # if there is no requiredPlatform... place this task into all queues...
    for aPlatform, aQueue in platformQueues.items() :
      await cutelogDebug(f"stored task event on {aPlatform} queue", name="dispatcher")
      await aQueue.put(thisTaskEvent)

  # wait for this task to be dispatched...
  await cutelogDebug(f"waiting for thisTaskEvent ({type(thisTaskEvent)})", name="dispatcher")
  await thisTaskEvent.wait()

  potentialWorkerHosts = []
  for aTaskType in task['workers'] :
    if aTaskType not in workerQueues or len(workerQueues[aTaskType]) < 1 : 
      continue
    for aWorkerHost in workerQueues[aTaskType] :
      if requiredPlatform and aWorkerHost not in hostTypes[requiredPlatform] :
        continue
      potentialWorkerHosts.append(( aTaskType, aWorkerHost ))

  await cutelogDebug({ 
    'task'        : task,
    'workerHosts' : potentialWorkerHosts
  }, name="debug")

  if not potentialWorkerHosts :
    await cutelogDebug(f"No specialist workers or hosts found for this task... dropping the connection")
    await cutelogDebug(task)
    writer.close()
    await writer.wait_closed()
    return

  while True :
    #print(yaml.dump(potentialWorkers))
    leastLoadedTaskType, leastLoadedHost = potentialWorkerHosts[0]
    for aPotentialWorkerHost in potentialWorkerHosts :
      aTaskType, aHost = aPotentialWorkerHost
      if hostLoads[aHost] < hostLoads[leastLoadedHost] :
        leastLoadedHost     = aHost
        leaseLoadedTaskType = aTaskType
    taskWorker = await workerQueues[leastLoadedTaskType][leastLoadedHost].get()
    workerQueues[leastLoadedTaskType][leastLoadedHost].task_done()

    try :
      workerName   = taskWorker['workerName']
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
  estimatedLoad = 0.5
  if 'estimatedLoad' in task : estimatedLoad = task['estimatedLoad']

  hostLoads[leastLoadedHost] += estimatedLoad

  while not workerReader.at_eof() :
    try :
      data = await workerReader.readuntil()
    except :
      await cutelogDebug(
        f"Worker {workerAddr!r} closed connection",
        name=f"{leastLoadedTaskType}.{workerName}.{leastLoadedHost}"
      )
      break

    message = data.decode()
    await cutelogDebug(
      f"Received [{message!r}] from {workerAddr!r}",
      name=f"{leastLoadedTaskType}.{workerName}.{leastLoadedHost}"
    )
    await cutelogDebug(
      f"Echoing: [{message!r}] to {addr!r}",
      name=f"{leastLoadedTaskType}.{workerName}.{leastLoadedHost}"
    )
    await cutelog(message)
    if 'returncode' in message :
      writer.write(data)
      #writer.write(b"\n")
      await writer.drain()

  await cutelogDebug(f"Closing the connection to {addr!r}")
  writer.close()
  await writer.wait_closed()

async def handleConnection(reader, writer) :
  """
  Handle one connection ...

  There are four types of JSON task messages:

  - monitor load information  : handled by `handleMonitorConnection`

  - worker registration       : handled by `handleWorkerConnection`

  - worker query              : handled by `handleQueryConnection`

  - new task request          : handled by `handleTaskRequestConnection`

  For each JSON task message, the `type` key MUST exist:

    - type      (one of `monitor`, `worker`, `workerQuery`, `taskRequest`)

  """
  addr = writer.get_extra_info('peername')
  await cutelogDebug(f"Handling new connection from {addr!r}")

  # read task type
  taskJson = await reader.readuntil()
  task = {}
  if taskJson :
    task = json.loads(taskJson.decode())

  if 'type' in task :
    # Handle this type of connection...

    if task['type'] == 'monitor' :
      # IF task is a monitor... start recording workloads for this host
      await handleMonitorConnection(task, reader, writer)

    elif task['type'] == 'worker' :
      # ELSE IF task is a worker... place the reader/writer in a worker queue
      await handleWorkerConnection(task, addr, reader, writer)

    elif task['type'] == 'workerQuery' :
      # ELSE IF task is a query about types of workers... check the worker queue
      await handleQueryConnection(task, reader, writer)

    elif task['type'] == 'taskRequest' :
      # ELSE task is a request... get a worker and echo the results
      await handleTaskRequestConnection(task, taskJson, addr, reader, writer)

  await cutelogDebug("Waiting for a new connection...")
