
import click

@click.command()
@click.pass_context
def run(ctx) :
  print("running the compute farm")
