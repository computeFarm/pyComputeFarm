
import click
from pathlib import Path
import sys
import tempfile
import yaml

import rcf.config
import rcf.roles

def createFilesFor(aRole, rFiles, rVars, aDir, config, secrets) :
  for aFile in rFiles :
    contents = rcf.roles.loadResourceFor(aRole, aFile['src'])
    theTargetFile = aDir / aFile['dest'].format_map(rVars)
    theTargetMode = 0o0644
    if 'mode' in aFile :
      theTargetMode = aFile['mode']
    if aFile['src'].endswith('.j2') :
      rcf.roles.jinjaFile(contents, theTargetFile, config, secrets)
    else :
      rcf.roles.copyFile(contents, theTargetFile)

def createLocalResourcesFor(aRole, gVars, aHost, aDir, config, secrets) :
  rTasks = rcf.roles.loadTasksFor(aRole)
  rVars  = {}
  rcf.roles.mergeVars(rVars, gVars)
  if 'vars' in rTasks :
    rcf.roles.mergeVars(rVars, rTasks['vars'])

  if 'targetDirs' in rTasks :
    for aTargetDir in rTasks['targetDirs'] :
      theTargetDir = aDir / aTargetDir.format_map(rVars)
      theTargetDir.mkdir(parents=True, exist_ok=True)

  if 'files' in rTasks :
    rFiles = rTasks['files']
    createFilesFor(aRole, rTasks['files'], rVars, aDir, config, secrets)

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

  gTasks  = rcf.roles.loadTasksFor()
  gVars   = {}
  if 'vars' in gTasks :
    rcf.roles.mergeVars(gVars, gTasks['vars'])


  hList   = gConfig['hostList']
  for aHost in hList :
    hConfig = config[aHost]
    hDir = tmpDir / aHost
    hDir.mkdir()
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