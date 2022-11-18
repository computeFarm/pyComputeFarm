
import click
import importlib.resources
import jinja2
from pathlib import Path
import platform
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

def jinjaFile(fromTemplate, toPath, config, secrets) :
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

def createRunCommandFor(aRole, rCmds, rVars, aDir, config, secrets) :
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
  jinjaFile(cmdTemplate, theTargetFile, config, secrets)
  config['rCmds'] = None
  theTargetFile.chmod(0o0755)

def createFilesFor(aRole, rFiles, rVars, aDir, config, secrets) :
  for aFile in rFiles :
    contents = loadResourceFor(aRole, aFile['src'])
    theTargetFile = aDir / aFile['dest'].format_map(rVars)
    if aFile['src'].endswith('.j2') :
      jinjaFile(contents, theTargetFile, config, secrets)
    else :
      copyFile(contents, theTargetFile)
    theTargetMode = 0o0644
    if 'mode' in aFile :
      theTargetMode = aFile['mode']
    theTargetFile.chmod(theTargetMode)

def createLocalResourcesFor(aRole, gVars, aHost, aDir, config, secrets) :
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
    createFilesFor(aRole, rTasks['files'], rVars, aDir, config, secrets)

  if 'commands' in rTasks :
    createRunCommandFor(aRole, rTasks['commands'], rVars, aDir, config, secrets)

  if 'workers' in config :
    if aRole in config['workers'] :
      if 'list' in rTasks and 'list' in config['workers'][aRole] :
        for aWorker in config['workers'][aRole]['list'] :
          rVars['aWorker'] = aWorker
          createFilesFor(aRole, rTasks['list'], rVars, aDir, config, secrets)

def createLocalResources(setupConfig, config, secrets) :
  setupConfig['tmpDir'] = tempfile.mkdtemp(prefix='rcf-')
  tmpDir = Path(setupConfig['tmpDir'])
  gConfig = config['globalConfig']

  gTasks  = loadTasksFor()
  gVars   = {}
  if 'vars' in gTasks :
    mergeVars(gVars, gTasks['vars'])

  hList   = gConfig['hostList']
  for aHost in hList :
    hConfig = config[aHost]
    hDir = tmpDir / aHost
    hDir.mkdir()
    if aHost == platform.node() :
      createLocalResourcesFor(
        'taskManager', gVars, aHost, hDir, hConfig, secrets[aHost]
      )
    if 'workers' in hConfig :
      createLocalResourcesFor(
        'allWorkers', gVars, aHost, hDir, hConfig, secrets[aHost]
      )
      for aWorker in hConfig['workers'] :
        createLocalResourcesFor(
          aWorker, gVars, aHost, hDir, hConfig, secrets[aHost]
        )

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
  #if rcf.config.hasVaults(configPath) :
  #  passPhrase = rcf.config.askForPassPhrase()
  rcf.config.loadGlobalConfiguration(config, secrets, passPhrase=passPhrase)
  rcf.config.loadConfigurationFor(config, secrets, passPhrase=passPhrase)
  print("----------------------------------------------------")
  print(yaml.dump(config))
  print("----------------------------------------------------")
  #print(yaml.dump(secrets))
  #print("----------------------------------------------------")
  setupConfig = {}
  createLocalResources(setupConfig, config, secrets)
  print(yaml.dump(setupConfig))