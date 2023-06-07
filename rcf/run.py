"""
The click command to run a computeFarm.

This command expects an (optional) list of hosts on which this computeFarm
should be run.

If no list is provided, all known (configured) hosta that are currently running
are used.


"""

import click
import datetime
from multiprocessing import Process
import os
import pexpect
import platform
import sys
from threading import Thread
import time
import yaml

from rcf.config import ( loadConfig, loadTasksFor, mergeVars )

# We *could* use an asycnio pattern... however the tasks for each host are
# fundamentally synchronous and must be done in a specific order. The only
# asyncio boost we might get would be from co-routines yeilding to
# co-routines working on a *different* host.

# Unforutnately, ssh and in particular pexpect based ssh is *not*
# async-able (the `async_=True` option is only a halfway measure and, in
# particular, the logfiles *must* all be synchronous as pexepct does *not*
# await any file io).

# This strongly suggests we need to consider either:
#   1. python multi-threading
# OR
#   2. python multi-processing

# We do not have any synchronization issuses *between* the work on any
# given hosts. Essentially all of the required state is loaded as
# configuration. For a given host all processing is independent of any
# other host. So we load the configuration, and start a thread/process
# going to work on each host and then wait for these threads/processes to
# complete.

# In particular, none of our work is particularly CPU bound, this suggests
# the difference between the use of threads vs processes is minimal (for
# our use) and so we *will* use threads (usually scheduled, in our linux
# case, by the OS).

timeNow = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%s.%f')

def runCommandOnHost(aHost, runCmdPath, sshOpts, config, secrets, logFile, timeOut=30) :
  """
  Run one command on a remote host using Python `pexpect` to deal with password prompts.
  
  Collect the stdout and stderr output and the exit result.
  """
  logFile.write(f"running command [{runCmdPath}] on {aHost}\n")
  if timeOut is None : logFile.write("running with no timeout!\n")
  else : logFile.write(f"running with timeOut = {timeOut}\n")
  connectionCmd = "ssh {sshOpts} {ssh_user}@{aHost} {runCmdPath}"
  runCmd = pexpect.spawn(
    connectionCmd.format(
      sshOpts=sshOpts,
      aHost=aHost,
      runCmdPath=runCmdPath,
      ssh_user=config['ssh_user'],
      ssh_home=config['ssh_home'],
      timeout=timeOut
    ),
    encoding='utf-8'
  )
  runCmd.logfile_read = logFile
  while True :
    pResult = runCmd.expect([
      "Enter passphrase for key", pexpect.EOF, pexpect.TIMEOUT
    ], timeout=timeOut)
    if pResult == 0 :
      runCmd.sendline(secrets['ssh_pass'])
    elif pResult == 1 :
      logFile.write("EOF\n")
      break
    elif pResult == 2 :
      logFile.write("TIMED OUT\n")
      break
    else :
      logFile.write("Unknown return\n")
      break
  if not runCmd.eof() : logFile.write(runCmd.read())
  runCmd.close()
  logFile.write(f"  exit status: {runCmd.exitstatus}\n")
  logFile.write(f"signal status: {runCmd.signalstatus}\n")
  return runCmd.exitstatus

def mountSshfsOnAHost(aHost, gVars, config, secrets, logFileBase) :
  """
  Mount an sshfs directory on the host `aHost`.

  We use ssh/sshfs optimizations based on: 

    https://blog.ja-ke.tech/2019/08/27/nas-performance-sshfs-nfs-smb.html

  and

    https://www.admin-magazine.com/HPC/Articles/Sharing-Data-with-SSHFS

  We use the second links suggested SSHFS OPT1 and should consider SSHFS OPT2
  (unfortunately the OPT2 requires MTU changes)
  """
  print(f"Mount sshfs on host {aHost}")
  runCmdPath = "sshfs -o ssh_command=ssh -o Ciphers=aes128-ctr -o cache=yes -o auto_cache -o compression=no -o ServerAliveInterval=60 -f -d {ssh_user}@{filesHost}:{filesOrig} {filesDest}".format(
    ssh_user=config['ssh_user'],
    filesHost=config['files']['host'],
    filesOrig=config['files']['orig'].format_map(gVars),
    filesDest=config['files']['dest'].format_map(gVars)
  )
  exitStatus = 0
  with open(str(logFileBase)+'-mount', "w") as logFile :
    exitStatus = runCommandOnHost(aHost, runCmdPath, "-t -o ServerAliveInterval=60", config, secrets, logFile, timeOut=None)
  print(f"Mounted sshfs on host {aHost} (exit status: {exitStatus})")

def unmountSshfsOnAHost(mountProcess, aHost, gVars, config, secrets, logFileBase) :
  """
  Unmount an sshfs directory on the host `aHost`.
  """
  print(f"Unmount sshfs on host {aHost}")

  runCmdPath = "fusermount -z -u {filesDest}".format(
    filesDest=config['files']['dest'].format_map(gVars)
  )
  exitStatus = 0
  with open(str(logFileBase)+'-unmount', "w") as logFile :
    # REALLY WE NEED TO STOP ALL OF THE WORKERS FIRST!!!
    # can't beat the old adage.... sync sync and sync again! (FLUSH those caches!)
    exitStatus = runCommandOnHost(aHost, "sync", "-t", config, secrets, logFile)
    exitStatus = runCommandOnHost(aHost, "sync", "-t", config, secrets, logFile)
    exitStatus = runCommandOnHost(aHost, "sync", "-t", config, secrets, logFile)
    exitStatus = runCommandOnHost(aHost, runCmdPath, "-t", config, secrets, logFile)
  print(f"Unmounted sshfs on host {aHost} (exit status: {exitStatus})")
  if mountProcess.is_alive() :
    time.sleep(5)
    if mountProcess.is_alive() :
      mountProcess.terminate()
      if mountProcess.is_alive() :
        mountProcess.kill()
      print(f"TERMINATED daemon thread: mounted sshfs on host {aHost}")

def startAHost(aHost, gVars, config, secrets, logFileBase) :
  """
  Start the host `aHost` by running the `start_computeFarm` script installed by
  the rcf setup stage.
  """
  print(f"Starting host {aHost}")
  runCmdPath = os.path.join(
    "{pcfHome}".format_map(gVars),
    'bin', 'start_computeFarm'
  )
  exitStatus = 0
  with open(str(logFileBase)+'-start', "w") as logFile :
    exitStatus = runCommandOnHost(aHost, runCmdPath, "", config, secrets, logFile)
  print(f"Started host {aHost} (exit status:: {exitStatus})")

def stopAHost(aHost, gVars, config, secrets, logFileBase) :
  """
  Stop the host `aHost` by running the `stop_computeFarm` script installed by
  the rcf setup stage.
  """
  print(f"Stopping host {aHost}")
  runCmdPath = os.path.join(
    "{pcfHome}".format_map(gVars),
    'bin', 'stop_computeFarm'
  )
  exitStatus = 0
  with open(str(logFileBase)+'-stop', "w") as logFile :
    exitStatus = runCommandOnHost(aHost, runCmdPath, "", config, secrets, logFile)
  print(f"Stopped host {aHost} (exit status: {exitStatus})")

def isHostUp(aHost) :
  """
  Ping the host `aHost` and return True if the host is "up".
  """
  pingCmd = pexpect.spawn(f"ping {aHost}")
  pResult = pingCmd.expect_exact([
    " Destination Host Unreachable",
    "64 bytes from "
  ])
  pingCmd.terminate(force=True)
  return pResult == 1

def runHosts(someHosts, config, secrets) :
  """
  Start all known (and "up") hosts by creating and running:
    - a sshfs start thread (using `mountSshfsOnAHost`)
    - a start host thread (using `startAHost`)
  
  Then wait for the user to type `stop` at the read prompt.

  The for all known (and "up") hosts create and run:
    - a sshfs stop thread (using `unmountSshfsOnAHost`)
    - a stop host thread (using `stopAHost`)

  Then wait for all threads to finish.
  """
  gConfig = config['globalConfig']
  gTasks  = loadTasksFor()
  gVars   = {}
  if 'vars' in gTasks :
    mergeVars(gVars, gTasks['vars'])
  hList = gConfig['hostList']
  if someHosts : hList = list(someHosts)
  mountProcesses = []
  unmountThreads = []
  startThreads   = []
  stopThreads    = []
  for aHost in hList :
    if not isHostUp(aHost) :
      print(f"Host {aHost} is not up")
      continue

    logFileBase = os.path.join("logs", (aHost + '-' + timeNow) )
    os.makedirs(os.path.dirname(logFileBase), exist_ok=True)

    mountProcess = Process(target=mountSshfsOnAHost, args=[
      aHost, gVars, config[aHost], secrets[aHost], logFileBase
    ])
    mountProcesses.append(mountProcess)
    unmountThreads.append(Thread(target=unmountSshfsOnAHost, args=[
      mountProcess, aHost, gVars, config[aHost], secrets[aHost], logFileBase
    ]))
    startThreads.append(Thread(target=startAHost, args=[
      aHost, gVars, config[aHost], secrets[aHost], logFileBase
    ]))
    stopThreads.append(Thread(target=stopAHost, args=[
      aHost, gVars, config[aHost], secrets[aHost], logFileBase
    ]))

  for aProcess in mountProcesses : aProcess.start()
  for aThread  in startThreads   : aThread.start()
  while True :
    response = input("Type 'stop' to stop the compute farm: ")
    if response == 'stop' : break
  for aThread  in stopThreads    : aThread.start()
  for aThread  in unmountThreads : aThread.start()

  for aThread  in unmountThreads : aThread.join()
  for aThread  in stopThreads    : aThread.join()
  for aThread  in startThreads   : aThread.join()
  for aProcess in mountProcesses : aProcess.join()

@click.command()
@click.argument('hosts', nargs=-1)
@click.pass_context
def run(ctx, hosts) :
  """Run HOSTS.

  If no hosts are provided, run all configured hosts that are up.
  """

  config, secrets = loadConfig(ctx)

  runHosts(hosts, config, secrets)
