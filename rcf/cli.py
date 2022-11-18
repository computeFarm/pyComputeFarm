
import click

# see: https://click.palletsprojects.com/en/8.1.x/

import rcf.setup
import rcf.run
import rcf.cryption
import rcf.config

@click.group()
@click.option('-c', '--config', default='config',
  help="Configuration directory path (default: 'config')"
)
@click.pass_context
def cli(ctx, config) :
  ctx.ensure_object(dict)
  ctx.obj['configPath'] = config

cli.add_command(rcf.setup.setup)
cli.add_command(rcf.run.run)
cli.add_command(rcf.cryption.encrypt)
cli.add_command(rcf.cryption.decrypt)
