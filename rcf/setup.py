
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
  rcf.config.loadGlobalConfiguration(config)
  rcf.config.loadConfigurationFor(config)
  print("----------------------------------------------------")
  print(yaml.dump(config))
  print("----------------------------------------------------")
