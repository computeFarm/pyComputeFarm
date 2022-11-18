
import base64
import click
from pathlib import Path
import secrets
import sys

import rcf.config

@click.command()
@click.argument('path')
@click.pass_context
def encrypt(ctx, path) :
  print(f"encrypting {path}")
  path = Path(path)
  if not path.is_file() :
    print(f"ERROR: the path [{path}] is not a file")
    sys.exit(1)
  with open(path, 'rb') as file :
    contents = file.read()
  passPhrase = rcf.config.askForPassPhrase(isNew=True)
  eContents = rcf.config.encrypt(contents, passPhrase)
  with open(path, 'w') as file :
    file.write(eContents)
  print("Encryption successful")

@click.command()
@click.argument('path')
@click.pass_context
def decrypt(ctx, path) :
  print(f"decrypting {path}")
  path = Path(path)
  if path.exists() and not path.is_file() :
    print(f"ERROR: the path [{path}] is not a file")
    sys.exit(1)
  with open(path, 'r') as file :
    eContents = file.read()
  passPhrase = rcf.config.askForPassPhrase()
  contents = rcf.config.decrypt(eContents, passPhrase)
  with open(path, 'wb') as file :
    file.write(contents)
  print("Decryption successful")
