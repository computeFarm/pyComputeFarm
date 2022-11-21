
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
import yaml

import rcf.config

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

def createRunCommandFor(aRole, rCmds, rVars, aHost, aDir, config, secrets, logFile) :
  cmdTemplate = """#!/bin/sh

  {% for aCmd in rCmds %}
  echo ""
  echo "---------------------------------------------------------"
  echo Running command {{ aCmd.name }}
  echo ""
  echo "cmd: [{{ aCmd.cmd }}]"
  echo "---------------------------------------------------------"
  cd {{ aCmd.chdir }}
  {{ aCmd.cmd }}
  echo "---------------------------------------------------------"
  {% endfor %}
"""
  theTargetFile = aDir / "{pcfHome}".format_map(rVars) / 'tmp' / ('run_command_'+aRole)
  for aCmd in rCmds :
    for aKey, aValue in aCmd.items() :
      aCmd[aKey] = aValue.format_map(rVars)
  config['rCmds'] = rCmds
  jinjaFile(cmdTemplate, theTargetFile, config, secrets, logFile)
  config['rCmds'] = None
  theTargetFile.chmod(0o0755)

def runCommandFor(aRole, rVars, aHost, config, secrets, logFile) :
  runCmdPath = os.path.join("{pcfHome}".format_map(rVars), "tmp", 'run_command_'+aRole)
  runCmd = pexpect.spawn(
    "ssh {ssh_user}@{aHost} {runCmdPath}".format(
      aRole=aRole,
      aHost=aHost,
      runCmdPath=runCmdPath,
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
    createRunCommandFor(aRole, rTasks['commands'], rVars, aHost, aDir, config, secrets, logFile)

  if 'workers' in config :
    if aRole in config['workers'] :
      if 'list' in rTasks and 'list' in config['workers'][aRole] :
        for aWorker in config['workers'][aRole]['list'] :
          rVars['aWorker'] = aWorker
          createFilesFor(aRole, rTasks['list'], rVars, aHost, aDir, config, secrets, logFile)

def runCommandsFor(aRole, gVars, aHost, config, secrets, logFile) :
  logFile.write(f"creating lobal resources for {aRole} on {aHost}\n")
  rTasks = loadTasksFor(aRole)
  rVars  = {}
  mergeVars(rVars, gVars)
  if 'vars' in rTasks :
    mergeVars(rVars, rTasks['vars'])
  if 'commands' in rTasks :
    runCommandFor(aRole, rVars, aHost, config, secrets, logFile)

def createLocalResourcesForHost(tmpDir, aHost, gVars, config, secrets, logFile) :
  logFile.write(f"creating local resources for {aHost}\n")
  hDir = tmpDir / aHost
  hDir.mkdir(parents=True, exist_ok=True)

  if aHost == platform.node() :
    createLocalResourcesFor(
      'taskManager', gVars, aHost, hDir, config, secrets, logFile
    )
  if 'workers' in config :
    createLocalResourcesFor(
      'allWorkers', gVars, aHost, hDir, config, secrets, logFile
    )
    for aWorker in config['workers'] :
      createLocalResourcesFor(
        aWorker, gVars, aHost, hDir, config, secrets, logFile
      )

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

def runCommandsForHost(tmpDir, aHost, gVars, config, secrets, logFile) :
  logFile.write(f"running commands on {aHost}\n")
  if aHost == platform.node() :
    runCommandsFor('taskManager', gVars, aHost, config, secrets, logFile)
  if 'workers' in config :
    runCommandsFor('allWorkers', gVars, aHost, config, secrets, logFile)
    for aWorker in config['workers'] :
      runCommandsFor(aWorker, gVars, aHost, config, secrets, logFile)

def setupAHost(tmpDir, aHost, gVars, config, secrets) :
  print(f"Setting up host {aHost} in {tmpDir}/{aHost}")
  timeNow = datetime.datetime.now()
  logFilePath = Path("logs") / (aHost + '-' + timeNow.strftime('%Y-%m-%d_%H-%M-%s.%f'))
  logFilePath.parent.mkdir(parents=True, exist_ok=True)
  with open(logFilePath, "w") as logFile :
    createLocalResourcesForHost(tmpDir, aHost, gVars, config, secrets, logFile)
    rsyncResourcesForHost(tmpDir, aHost, gVars, config, secrets, logFile)
    runCommandsForHost(tmpDir, aHost, gVars, config, secrets, logFile)

def isHostUp(aHost) :
  pingCmd = pexpect.spawn(f"ping {aHost}")
  pResult = pingCmd.expect_exact([
    " Destination Host Unreachable",
    "64 bytes from "
  ])
  pingCmd.terminate(force=True)
  return pResult == 1

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
  for aHost in hList :
    if isHostUp(aHost) :
      setupAHost(tmpDir, aHost, gVars, config[aHost], secrets[aHost])
