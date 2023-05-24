"""
The click command used to setup and run a computeFarm.

Expects a (optional) list of hosts to be included in this run of the
computeFarm.

If no list of hosts is provided, all known (configured) hosts that are currently
running are used.
"""


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
