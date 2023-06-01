"""
Run the taskManager by dealing with the command line arguments and then running
the tcpTaskServer.
"""

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

  # start the taskRequest dispatcher... (and run forever)
  dispatcherTask = asyncio.create_task(dispatcher())

  taskManager = config['taskManager']
  server = await asyncio.start_server(
    handleConnection, taskManager['interface'], taskManager['port']
  )

  addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
  print(f"TaskManager serving on {addrs}")
  await cutelogInfo(f"TaskManager serving on {addrs}")

  async with server :
    await server.serve_forever()
  dispactherTask.cancel() # once the server has finished... cancel the dispatcher.

def runTaskManager() :
  """
  Provide a central task manager for a compute farm by listening for JSON RPC
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

  if 'files' in config :
    if 'orig' in config['files'] :
      fileLocations['orig'] = config['files']['orig']
    if 'dest' in config['files'] :
      fileLocations['dest'] = config['files']['dest']

  try :
    asyncio.run(tcpTaskServer(config))
  except :
    #pass
    print("Caught and ignored exception")
    print(traceback.format_exc())

if __name__ == "__main__" :
  sys.exit(runTaskManager())
