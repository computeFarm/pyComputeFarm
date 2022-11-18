
import click
import sys
import yaml

import rcf.config

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
  print("----------------------------------------------------")
  print(yaml.dump(config))
  print("----------------------------------------------------")
  #print(yaml.dump(secrets))
  #print("----------------------------------------------------")
