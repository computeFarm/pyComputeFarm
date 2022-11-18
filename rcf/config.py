
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import getpass
import logging
from pathlib import Path
import secrets
import yaml

def mergeYamlData(yamlData, newYamlData, thePath) :
  """ This is a generic Python merge. It is a *deep* merge and handles
  both dictionaries and arrays """

  if type(yamlData) is None :
    logging.error("yamlData should NEVER be None ")
    logging.error("Stoping merge at {}".format(thePath))
    return

  if type(yamlData) != type(newYamlData) :
    logging.error("Incompatible types {} and {} while trying to merge YAML data at {}".format(type(yamlData), type(newYamlData), thePath))
    logging.error("Stoping merge at {}".format(thePath))
    return

  if type(yamlData) is dict :
    for key, value in newYamlData.items() :
      if key not in yamlData :
        yamlData[key] = value
      elif type(yamlData[key]) is dict :
        mergeYamlData(yamlData[key], value, thePath+'.'+key)
      elif type(yamlData[key]) is list :
        for aValue in value :
          yamlData[key].append(aValue)
      else :
        yamlData[key] = value
  elif type(yamlData) is list :
    for value in newYamlData :
      yamlData.append(value)
  else :
    logging.error("YamlData MUST be either a dictionary or an array.")
    logging.error("Stoping merge at {}".format(thePath))
    return

def getConfigPath(config, sectionName) :
  if 'globalConfig' not in config :
    print(f"ERROR({sectionName}): no globalConfig defined yet")
    sys.exit(1)
  gConfig = config['globalConfig']
  if 'configPath' not in gConfig :
    print(f"ERROR({sectionName}): no config path defined yet")
    sys.exit(1)
  return gConfig['configPath']

def loadGlobalConfiguration(config) :

  # start by loading the global configuration
  configPath = getConfigPath(config, 'loadGlobalConfiguration')

  globalConfigDir = Path(configPath) / 'globalConfig'
  if not globalConfigDir.is_dir() :
    print(f"ERROR(loadGlobalConfiguraion): no 'globalConfig' directory found in config path [{configPath}]")
    sys.exit(1)

  configFile = globalConfigDir / 'config'
  if not configFile.is_file() :
    print(f"ERROR(loadGlobalConfiguraion): no 'config' file in the config path [{configPath}/globalConfig]")
    sys.exit(1)

  with open(configFile, 'r') as cf :
    gConfig = yaml.safe_load(cf.read())
  gConfig['configPath'] = configPath
  mergeYamlData(config['globalConfig'], gConfig, 'globalConfig')

  # now determine the list of hosts
  hostList = []
  for anItem in Path(configPath).iterdir() :
    if not anItem.is_dir() : continue
    if str(anItem).endswith('globalConfig') : continue
    hostList.append(str(anItem.name))
  hostList.sort()

  config['globalConfig']['hostList'] = hostList

def loadConfigurationFor(config, hosts=None) :
  if hosts is None :
    hosts = config['globalConfig']['hostList']
  if not isinstance(hosts, list) :
    hosts = [ str(hosts) ]

  configPath = Path(config['globalConfig']['configPath'])
  for aHost in hosts :
    if aHost not in config : config[aHost] = {}
    mergeYamlData(config[aHost], config['globalConfig'], aHost)

    hostPath = configPath / aHost
    for anItem in hostPath.iterdir() :
      if str(anItem).endswith('vault') : continue
      if anItem.is_file() :
        with open(anItem, 'r') as cf :
          hostConfig = yaml.safe_load(cf.read())
        mergeYamlData(config[aHost], hostConfig, aHost)

def hasVaults(configPath) :
  vaults = Path(configPath).glob('*/vault')
  if len(list(vaults)) < 1 :
    return False
  return True

def askForKey(salt, isNew=False) :
  passPhrase = getpass.getpass("Vault pass phrase: ")
  if isNew :
    passPhrase2 = getpass.getpass("Confirm pass phrase: ")
    if passPhrase != passPhrase2 :
      print("Pass phrases do not match")
      return None

  # see: https://www.thepythoncode.com/article/encrypt-decrypt-files-symmetric-python#file-encryption-with-password
  kdf  = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
  return kdf.derive(password.encode())

def encrypt(contents, key) :
  pass

def decrypt(contents, key) :
  pass