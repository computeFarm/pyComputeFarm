
import click

from rcf.config import loadConfig
from rcf.setup  import setupHosts
from rcf.run    import runHosts

@click.command()
@click.argument('hosts', nargs=-1)
@click.pass_context
def sar(ctx, hosts) :
  """Setup and run (sar) HOSTS.

  If no hosts are provided, setup and run (sar) all configured hosts that
  are up.
  """
  config, secrets = loadConfig(ctx)

  setupHosts(hosts, config, secrets)

  print("----------------------------------------------------")

  runHosts(hosts, config, secrets)
