
import click
import datetime
import importlib.resources
import jinja2
from pathlib import Path
import pexpect
import platform
import os
import sys
import tempfile
from threading import Thread
import yaml

import rcf.config

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

def loadResourceFor(aRole, aResource) :
  if aRole :
    contents = importlib.resources.read_text('rcf.roleResources.'+aRole, aResource)
  else :
    contents = importlib.resources.read_text('rcf.roleResources', aResource)
  return contents

def loadTasksFor(aRole=None) :
  taskYaml = loadResourceFor(aRole, 'tasks.yaml')
  return yaml.safe_load(taskYaml)

def mergeVars(oldVars, newVars) :
  for aKey, aValue in newVars.items() :
    oldVars[aKey] = aValue.format(oldVars)

def copyFile(fileContents, toPath) :
  with open(toPath, 'w') as toFile :
    toFile.write(fileContents)

def jinjaFile(fromTemplate, toPath, config, secrets, logFile) :
  env = {}
  rcf.config.mergeYamlData(env, config,  '.')
  rcf.config.mergeYamlData(env, secrets, '.')
  try:
    template = jinja2.Template(fromTemplate)
    fileContents = template.render(env)
    with open(toPath, 'w') as toFile :
      toFile.write(fileContents)
  except Exception as err:
    print(f"Could not render the Jinja2 template")
    print(err)
    print("==========================================================")
    print(fromTemplate)
    print("==========================================================")
    print(yaml.dump(env))
    print("==========================================================")

def createRunCommandFor(
  aRole, rCmds, rVars, theTargetFile,
  aHost, aDir, config, secrets, logFile
) :
  cmdTemplate = """#!/bin/sh

  {% for aCmd in rCmds %}
  echo ""
  echo "---------------------------------------------------------"
  {% if aCmd.name %}echo Running command {{ aCmd.name }}{% endif %}
  echo ""
  echo "cmd: [{{ aCmd.cmd }}]"
  echo "---------------------------------------------------------"
  {% if aCmd.chdir %}cd {{ aCmd.chdir }}{% endif %}
  {{ aCmd.cmd }}
  echo "---------------------------------------------------------"
  {% endfor %}
"""
  for aCmd in rCmds :
    for aKey, aValue in aCmd.items() :
      aCmd[aKey] = aValue.format_map(rVars)
  config['rCmds'] = rCmds
  jinjaFile(cmdTemplate, theTargetFile, config, secrets, logFile)
  config['rCmds'] = None
  theTargetFile.chmod(0o0755)

def createFilesFor(aRole, rFiles, rVars, aHost, aDir, config, secrets, logFile) :
  logFile.write(f"creating files for {aRole} on {aHost}\n")
  for aFile in rFiles :
    contents = loadResourceFor(aRole, aFile['src'])
    theTargetFile = aDir / aFile['dest'].format_map(rVars)
    if aFile['src'].endswith('.j2') :
      jinjaFile(contents, theTargetFile, config, secrets, logFile)
    else :
      copyFile(contents, theTargetFile)
    theTargetMode = 0o0644
    if 'mode' in aFile :
      theTargetMode = aFile['mode']
    theTargetFile.chmod(theTargetMode)

def createLocalResourcesFor(aRole, gVars, aHost, aDir, config, secrets, logFile) :
  logFile.write(f"creating global resources for {aRole} on {aHost}\n")
  cmdTypes = {}
  rTasks = loadTasksFor(aRole)
  rVars  = {}
  mergeVars(rVars, gVars)
  if 'vars' in rTasks :
    mergeVars(rVars, rTasks['vars'])

  if 'targetDirs' in rTasks :
    for aTargetDir in rTasks['targetDirs'] :
      theTargetDir = aDir / aTargetDir.format_map(rVars)
      theTargetDir.mkdir(parents=True, exist_ok=True)

  if 'files' in rTasks :
    createFilesFor(aRole, rTasks['files'], rVars, aHost,  aDir, config, secrets, logFile)

  if 'commands' in rTasks :
    theTargetFile = aDir / "{pcfHome}".format_map(rVars) / 'tmp' / ('run_command_'+aRole)
    cmdTypes['commands'] = str(theTargetFile)
    createRunCommandFor(
      aRole, rTasks['commands'], rVars, theTargetFile,
      aHost, aDir, config, secrets, logFile
    )

  if 'start' in rTasks :
    theTargetFile = aDir / "{pcfHome}".format_map(rVars) / 'bin' / ('start_'+aRole)
    cmdTypes['start'] = str(theTargetFile)
    createRunCommandFor(
      aRole, rTasks['start'], rVars, theTargetFile,
      aHost, aDir, config, secrets, logFile
    )

  if 'stop' in rTasks :
    theTargetFile = aDir / "{pcfHome}".format_map(rVars) / 'bin' / ('stop_'+aRole)
    cmdTypes['stop'] = str(theTargetFile)
    createRunCommandFor(
      aRole, rTasks['stop'], rVars, theTargetFile,
      aHost, aDir, config, secrets, logFile
    )

  if 'workers' in config :
    if aRole in config['workers'] :
      if 'list' in rTasks and 'list' in config['workers'][aRole] :
        for aWorker in config['workers'][aRole]['list'] :
          rVars['aWorker'] = aWorker
          createFilesFor(aRole, rTasks['list'], rVars, aHost, aDir, config, secrets, logFile)

  return cmdTypes

def createStartStopRunCommandsForHost(cmdTypes, aHost, hDir, gVars, logFile) :
  logFile.write(f"creating start/stop/run commands for {aHost}\n")
  cmds = {}
  for aWorker, someCmds in cmdTypes.items() :
    for aCmd, aPath in someCmds.items() :
      if aCmd not in cmds : cmds[aCmd] = []
      cmds[aCmd].append('$HOME'+aPath.removeprefix(str(hDir)))
  cmdTemplate = '''
#!/bin/sh

{% for aCmd in cmds %}
{{ aCmd }}
{% endfor %}
  '''
  defaultTargetFiles = {
    'commands' : str(hDir / "{pcfHome}".format_map(gVars) / 'tmp' / 'run_commands'),
    'start'    : str(hDir / "{pcfHome}".format_map(gVars) / 'bin' / 'startComputeFarm'),
    'stop'     : str(hDir / "{pcfHome}".format_map(gVars) / 'bin' / 'stopComputeFarm')
  }
  targetFiles = {
    'hDir'     : str(hDir),
  }
  for aCmd, someCmds in cmds.items() :
    targetFiles[aCmd] = defaultTargetFiles[aCmd]
    if aCmd == 'stop' : someCmds.reverse()
    jinjaFile(cmdTemplate, targetFiles[aCmd], { 'cmds' : someCmds }, {}, logFile)
    os.chmod(targetFiles[aCmd], 0o0755)

  return targetFiles

def createLocalResourcesForHost(tmpDir, aHost, gVars, config, secrets, logFile) :
  logFile.write(f"creating local resources for {aHost}\n")
  hDir = tmpDir / aHost
  hDir.mkdir(parents=True, exist_ok=True)
  cmdTypes = {}

  if aHost == platform.node() :
    cmdTypes['taskManager'] = createLocalResourcesFor(
      'taskManager', gVars, aHost, hDir, config, secrets, logFile
    )
  if 'workers' in config :
    cmdTypes['allWorkers'] = createLocalResourcesFor(
      'allWorkers', gVars, aHost, hDir, config, secrets, logFile
    )
    for aWorker in config['workers'] :
      cmdTypes[aWorker] = createLocalResourcesFor(
        aWorker, gVars, aHost, hDir, config, secrets, logFile
      )
  return createStartStopRunCommandsForHost(cmdTypes, aHost, hDir, gVars, logFile)

def rsyncResourcesForHost(tmpDir, aHost, gVars, config, secrets, logFile) :
    logFile.write(f"rsyncing resouces to {aHost}\n")
    rsyncCmd = pexpect.spawn(
      "rsync -av {tmpDir}/{aHost}/ {ssh_user}@{aHost}:.".format(
        tmpDir=tmpDir,
        aHost=aHost,
        ssh_user=config['ssh_user']
      ),
      encoding='utf-8'
    )
    rsyncCmd.logfile_read = logFile
    while True :
      pResult = rsyncCmd.expect([
        "Enter passphrase for key", pexpect.EOF, pexpect.TIMEOUT
      ])
      if pResult == 0 :
        rsyncCmd.sendline(secrets['ssh_pass'])
      else : break

def runCommandsForHost(aHost, cmdPaths, config, secrets, logFile) :
  logFile.write(f"running commands on {aHost}\n")
  runCmd = pexpect.spawn(
    "ssh {ssh_user}@{aHost} {runCmdPath}".format(
      aHost=aHost,
      runCmdPath=cmdPaths['commands'].removeprefix(cmdPaths['hDir']+'/'),
      ssh_user=config['ssh_user']
    ),
    encoding='utf-8'
  )
  runCmd.logfile_read = logFile
  while True :
    pResult = runCmd.expect([
      "Enter passphrase for key", pexpect.EOF, pexpect.TIMEOUT
    ])
    if pResult == 0 :
      runCmd.sendline(secrets['ssh_pass'])
    else : break

def isHostUp(aHost) :
  pingCmd = pexpect.spawn(f"ping {aHost}")
  pResult = pingCmd.expect_exact([
    " Destination Host Unreachable",
    "64 bytes from "
  ])
  pingCmd.terminate(force=True)
  return pResult == 1

def setupAHost(tmpDir, aHost, gVars, config, secrets) :
  if not isHostUp(aHost) : return

  print(f"Setting up host {aHost} in {tmpDir}/{aHost}")
  timeNow = datetime.datetime.now()
  logFilePath = Path("logs") / (aHost + '-' + timeNow.strftime('%Y-%m-%d_%H-%M-%s.%f') + '-setup')
  logFilePath.parent.mkdir(parents=True, exist_ok=True)
  with open(logFilePath, "w") as logFile :
    cmdPaths = createLocalResourcesForHost(tmpDir, aHost, gVars, config, secrets, logFile)
    rsyncResourcesForHost(tmpDir, aHost, gVars, config, secrets, logFile)
    if 'commands' in cmdPaths :
      runCommandsForHost(aHost, cmdPaths, config, secrets, logFile)
    logFile.write(f"Finished setting up host {aHost}")
  print(f"Finished setting up host {aHost}")

@click.command()
@click.pass_context
def setup(ctx) :
  print("Setting up the compute farm")
  if 'configPath' not in ctx.obj :
    print("NO configPath provided!")
    sys.exit(1)

  configPath = ctx.obj['configPath']
  config     = rcf.config.initializeConfig(configPath)
  secrets    = rcf.config.initializeSecrets()
  passPhrase = None
  if rcf.config.hasVaults(configPath) :
    passPhrase = rcf.config.askForPassPhrase()
  rcf.config.loadGlobalConfiguration(config, secrets, passPhrase=passPhrase)
  rcf.config.loadConfigurationFor(config, secrets, passPhrase=passPhrase)
  if ctx.obj['verbose'] :
    print("----------------------------------------------------")
    print(yaml.dump(config))
  if ctx.obj['secrets'] :
    print("----------------------------------------------------")
    print(yaml.dump(secrets))
  print("----------------------------------------------------")

  tmpDir = Path(tempfile.mkdtemp(prefix='rcf-'))

  gConfig = config['globalConfig']
  gTasks  = loadTasksFor()
  gVars   = {}
  if 'vars' in gTasks :
    mergeVars(gVars, gTasks['vars'])

  hList = gConfig['hostList']
  workThreads = []
  for aHost in hList :
    workThreads.append(Thread(target=setupAHost, args=[
      tmpDir, aHost, gVars, config[aHost], secrets[aHost]
    ]))
  for aThread in workThreads : aThread.start()
  for aThread in workThreads : aThread.join()

