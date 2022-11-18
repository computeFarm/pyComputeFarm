
import base64
import click
import secrets

@click.command()
@click.pass_context
def encrypt(ctx) :
  print("encrypting a config vault")

@click.command()
@click.pass_context
def decrypt(ctx) :
  print("decrypting a config vault")

@click.command(
  help="Create a new Scrypt salt for use when encrypting and decrypting configuration vaults.",
  epilog="The salt provided should placed into your 'all/vars' file under the key 'scryptSalt' "
)
@click.pass_context
def newsalt(ctx) :
  aSalt = secrets.token_bytes(16)
  print(base64.b16encode(aSalt).decode())
