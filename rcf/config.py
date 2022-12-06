
import base64
import copy
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.exceptions import InvalidSignature
import getpass
import importlib.resources
from pathlib import Path
import secrets
import sys
import yaml

def mergeYamlData(yamlData, newYamlData, thePath) :
  """ This is a generic Python merge. It is a *deep* merge and handles
  both dictionaries and arrays """

  if type(yamlData) is None :
    print("ERROR(mergeYamlData): yamlData should NEVER be None ")
    print(f"ERROR(megeYamlData): Stopped merge at {thePath}")
    return

  if type(yamlData) != type(newYamlData) :
    print(f"ERROR(mergeYamlData): Incompatible types {type(yamlData)} and {type(newYamlData)} while trying to merge YAML data at {thePath}")
    print(f"ERROR(mergeYamlData): Stopped merge at {thePath}")
    return

  if type(yamlData) is dict :
    for key, value in newYamlData.items() :
      if key not in yamlData :
        yamlData[key] = copy.deepcopy(value)
      elif type(yamlData[key]) is dict :
        mergeYamlData(yamlData[key], value, thePath+'.'+key)
      elif type(yamlData[key]) is list :
        for aValue in value :
          yamlData[key].append(copy.deepcopy(aValue))
      else :
        yamlData[key] = copy.deepcopy(value)
  elif type(yamlData) is list :
    for value in newYamlData :
      yamlData.append(copy.deepcopy(value))
  else :
    print("ERROR(mergeYamlData): YamlData MUST be either a dictionary or an array.")
    print(f"ERROR(mergeYamlData): Stoping merge at {thePath}")
    return

def initializeConfig(aConfigPath) :
  return {
    'globalConfig' : {
      'configPath' : aConfigPath,
      'hostList'   : []
    }
  }

def initializeSecrets() :
  return {
    'globalConfig' : {}
  }

def loadGlobalConfiguration(config, secrets, passPhrase=None) :

  # Start by loading the global configuration from any *file* in
  # `config/globalConfig` which is not `vault`. Files are merged in
  # alphabetical order.

  configPath = Path(config['globalConfig']['configPath'])

  globalConfigDir = configPath / 'globalConfig'
  if not globalConfigDir.is_dir() :
    print(f"ERROR(loadGlobalConfiguraion): no 'globalConfig' directory found in config path [{configPath}]")
    sys.exit(1)

  items = list(globalConfigDir.iterdir())
  items.sort()
  for anItem in items :
    if not anItem.is_file() : continue
    with open(anItem, 'r') as cf :
      contents = cf.read()
    if not str(anItem).endswith('vault') :
      gConfig = yaml.safe_load(contents)
      mergeYamlData(config['globalConfig'], gConfig, 'globalConfig')
    elif passPhrase :
      decryptedContents = decrypt(contents, passPhrase)
      gSecrets = yaml.safe_load(decryptedContents)
      mergeYamlData(secrets['globalConfig'], gSecrets, 'secretGlobalConfig')

  # Now determine the list of hosts
  hostList = []
  for anItem in Path(configPath).iterdir() :
    if not anItem.is_dir() : continue
    if str(anItem).endswith('globalConfig') : continue
    hostList.append(str(anItem.name))
  hostList.sort()
  config['globalConfig']['hostList'] = hostList

def loadConfigurationFor(config, secrets, hosts=None, passPhrase=None) :
  if hosts is None :
    hosts = config['globalConfig']['hostList']
  if not isinstance(hosts, list) :
    hosts = [ str(hosts) ]

  configPath = Path(config['globalConfig']['configPath'])
  for aHost in hosts :
    if aHost not in config :
      config[aHost] = {}
      secrets[aHost] = {}
    mergeYamlData(config[aHost],  config['globalConfig'],  aHost)
    mergeYamlData(secrets[aHost], secrets['globalConfig'], 'secret-'+aHost)

    hostPath = configPath / aHost
    items = list(hostPath.iterdir())
    items.sort()
    for anItem in items :
      if not anItem.is_file() : continue
      with open(anItem, 'r') as cf :
        contents = cf.read()
      if not str(anItem).endswith('vault') :
        hostConfig = yaml.safe_load(contents)
        mergeYamlData(config[aHost], hostConfig, aHost)
      elif passPhrase :
        decryptedContents = decrypt(contents, passPhrase)
        hSecrets = yaml.safe_load(decryptedContents)
        mergeYamlData(secrets[aHost], hSecrets, 'secret-'+aHost)

def hasVaults(configPath) :
  vaults = Path(configPath).glob('*/vault')
  if len(list(vaults)) < 1 :
    return False
  return True

def askForPassPhrase(isNew=False) :
  passPhrase = getpass.getpass("Vault pass phrase: ")
  if isNew :
    passPhrase2 = getpass.getpass("Confirm pass phrase: ")
    if passPhrase != passPhrase2 :
      print("Pass phrases do not match")
      return None
  return passPhrase

# The next couple of definitions provide our encrypt/decript methods.
# These are based on the article:
# https://www.thepythoncode.com/article/encrypt-decrypt-files-symmetric-python#file-encryption-with-password

def getKey(salt, passPhrase) :
  kdf  = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
  return base64.urlsafe_b64encode(kdf.derive(passPhrase.encode()))

def encrypt(contents, passPhrase) :
  saltBytes = secrets.token_bytes(16)
  saltStr   = base64.b16encode(saltBytes).decode()
  key       = getKey(saltBytes, passPhrase)
  fernet    = Fernet(key)

  eContents = fernet.encrypt(contents)
  eContents = base64.urlsafe_b64decode(eContents)
  eContents = base64.b16encode(eContents).decode()

  eList = [
    'rcf-encrypted;1.0;Scrypt;Fernet',
    saltStr
  ]

  eLen = len(eContents)
  cur  = 0
  while cur < eLen :
    if eLen - cur < 50 :
      eList.append(eContents[cur : eLen])
    else :
      eList.append(eContents[cur : cur + 50])
    cur += 50

  return "\n".join(eList)

def decrypt(eContents, passPhrase) :
  eList = eContents.split()
  if eList[0] != "rcf-encrypted;1.0;Scrypt;Fernet" :
    print("ERROR: this is not an rcf encrypted file!")
    sys.exit(1)

  saltStr   = eList[1]
  saltBytes = base64.b16decode(saltStr.encode('utf-8'))
  key       = getKey(saltBytes, passPhrase)
  fernet    = Fernet(key)

  eContents = "".join(eList[2:])
  eContents = base64.b16decode(eContents)
  eContents = base64.urlsafe_b64encode(eContents)
  try :
    contents  = fernet.decrypt(eContents)
  except InvalidToken :
    print("ERROR: the pass phrase provided does not correspond")
    print("       to the pass phrase which encrypted the message")
    sys.exit(1)

  return contents

#########################################################################
# Resource management
#
def loadResourceFor(aRole, aResource) :
  try :
    if aRole :
      contents = importlib.resources.read_text('rcf.roleResources.'+aRole, aResource)
    else :
      contents = importlib.resources.read_text('rcf.roleResources', aResource)
  except Exception as err:
    print(f"ERROR loging resourceFor [{aRole}] [{aResource}]")
    print(repr(err))
    sys.exit(1)
  return contents

def loadTasksFor(aRole=None, config={}) :
  taskYaml = loadResourceFor(aRole, 'tasks.yaml')
  tasks = yaml.safe_load(taskYaml)
  if aRole :
    if 'tasks' in config :
      if aRole in config['tasks'] :
        mergeYamlData(tasks, config['tasks'][aRole], '.')
  return tasks

def mergeVars(oldVars, newVars) :
  for aKey, aValue in newVars.items() :
    oldVars[aKey] = aValue.format(oldVars)

def loadConfig(ctx) :
  print("Setting up the compute farm")
  if 'configPath' not in ctx.obj :
    print("NO configPath provided!")
    sys.exit(1)

  configPath = ctx.obj['configPath']
  config     = initializeConfig(configPath)
  secrets    = initializeSecrets()
  passPhrase = None
  if hasVaults(configPath) :
    passPhrase = askForPassPhrase()
  loadGlobalConfiguration(config, secrets, passPhrase=passPhrase)
  loadConfigurationFor(config, secrets, passPhrase=passPhrase)
  if ctx.obj['verbose'] :
    print("----------------------------------------------------")
    print(yaml.dump(config))
  if ctx.obj['secrets'] :
    print("----------------------------------------------------")
    print(yaml.dump(secrets))
  print("----------------------------------------------------")

  return (config, secrets)
