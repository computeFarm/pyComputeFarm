
import click

from rcf.config import loadConfig
from rcf.setup  import setupHosts
from rcf.run    import runHosts

@click.command()
@click.pass_context
def sar(ctx) :

  config, secrets = loadConfig(ctx)

  setupHosts(config, secrets)

  print("----------------------------------------------------")

  runHosts(config, secrets)
