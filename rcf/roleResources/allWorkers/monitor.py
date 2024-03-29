"""
Provide a regular source of load information so that the taskManager can do some
rudementary load balancing.
"""

import asyncio
import json
import platform
import os
import sys

def usage() :
  '''
usage: monitor

Start up a work load monitor

optional arguments

  -h, --host     TaskManager host
  -p, --port     TaskManager port
  -s, --scale    Normalized load scaling factor
  -i, --interval Reporting interval (seconds)
      --help     Show this help message and exit

  '''

  print(usage.__doc__)
  sys.exit(1)

def runMonitor() :
  """
  Connect to the specified task manager and provide load information every
  reporting interval (seconds).
  
  Among other things this acts as a heart beat for the computeFarm.
  """

  tmHost    = 'localhost'
  tmPort    = '8888'
  wScale    = 0.8
  maxLoad   = 1.0
  rInterval = 60

  i = 1
  while i < len(sys.argv) :
    anArg = sys.argv[i]
    print(anArg)
    if anArg == '-h' or anArg == '--host' :
      tmHost = sys.argv[i+1]
      i += 1
    elif anArg == '-p' or anArg == '--port' :
      tmPort = int(sys.argv[i+1])
      i += 1
    elif anArg == '-s' or anArg == '--scale' :
      wScale = float(sys.argv[i+1])
      i += 1
    elif anArg == '-i' or anArg == '--interval' :
      rInterval = int(sys.argv[i+1])
      i += 1
    elif anArg == '-l' or anArg == '--load' :
      maxLoad = float(sys.argv[i+1])
      i += 1
    elif anArg == '-h' or anArg == '--help' :
      usage()
    i += 1

  print(f"TaskMaster host: {tmHost}")
  print(f"TaskMaster port: {tmPort}")
  print(f"          Scale: {wScale}")
  print(f"       Max Load: {maxLoad}")
  print(f"Report interval: {rInterval}")

  async def workLoadMonitor(tmHost, thPort, wScale, rInterval) :
    for attempt in range(60) :
      try :
        reader, writer = await asyncio.open_connection( tmHost, tmPort )
        print(f"Connected to TaskManager on the {attempt} attempt")
        sys.stdout.flush()
        break
      except :
        reader = None
        writer = None
        print(f"Could not connect to taskManager on the {attempt} attempt")
        sys.stdout.flush()
      await asyncio.sleep(1)

    if reader is None or writer is None :
      print(f"Could NOT connect to the taskManager after {attempt} attempts")
      sys.stdout.flush()
      sys.exit(1)

    print("Sending monitor description to taskManager")
    hostName = platform.node()
    writer.write(json.dumps({
      'type'     : 'monitor',
      'taskType' : 'monitor',
      'host'     : hostName,
      'platform' : platform.system().lower(),
      'cpuType'  : platform.machine().lower(),
      'maxLoad'  : maxLoad
    }).encode())
    writer.write(b"\n")
    await writer.drain()

    numCpus = os.cpu_count()

    while True :
      wlOne, wlFive, wlFifteen = os.getloadavg()

      normOne = wlOne/(numCpus*wScale)
      normFive = wlFive/(numCpus*wScale)
      normFifteen = wlFifteen/(numCpus*wScale)

      print(f"               Num CPUs: {numCpus}")
      print(f"    One minute workload: {wlOne} ({wlOne/numCpus}) <{normOne}>")
      print(f"   Five minute workload: {wlFive} ({wlFive/numCpus}) <{normFive}>")
      print(f"Fifteen minute workload: {wlFifteen} ({wlFifteen/numCpus}) <{normFifteen}>")

      print("Sending workload update")
      writer.write(json.dumps({
        'type'      : 'monitor',
        'host'      : hostName,
        'numCpus'   : numCpus,
        'wlOne'     : wlOne,
        'wlFive'    : wlFive,
        'wlFifteen' : wlFifteen,
        'scale'     : wScale
      }).encode())
      writer.write(b"\n")
      try :
        await writer.drain()
      except :
        break

      await asyncio.sleep(rInterval)

    # close things down
    try :
      writer.close()
      await writer.wait_closed()
    except :
      pass

  asyncio.run(workLoadMonitor(tmHost, tmPort, wScale, rInterval))

if __name__ == "__main__" :
  sys.exit(runMonitor())
