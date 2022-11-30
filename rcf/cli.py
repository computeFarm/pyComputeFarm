
import click

# see: https://click.palletsprojects.com/en/8.1.x/

import rcf.setup
import rcf.run
import rcf.sar
import rcf.cryption
import rcf.config

@click.group()
@click.option('-c', '--config', default='config', show_default=True,
  help="Configuration directory path"
)
@click.option('-s', '--secrets', default=False, show_default=True,
  is_flag=True, help="Show the secrets"
)
@click.option('-v', '--verbose', default=False, show_default=True,
  is_flag=True, help="Be verbose"
)
@click.pass_context
def cli(ctx, config, secrets, verbose) :
  ctx.ensure_object(dict)
  ctx.obj['configPath'] = config
  ctx.obj['secrets']    = secrets
  ctx.obj['verbose']    = verbose

cli.add_command(rcf.setup.setup)
cli.add_command(rcf.run.run)
cli.add_command(rcf.sar.sar)
cli.add_command(rcf.cryption.encrypt)
cli.add_command(rcf.cryption.decrypt)
