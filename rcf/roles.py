
import importlib.resources
import jinja2
import yaml

import rcf.config

def copyFile(fileContents, toPath) :
  with open(toPath, 'w') as toFile :
    toFile.write(fileContents)

def jinjaFile(fromTemplate, toPath, config, secrets) :
  try:
    template = jinja2.Template(fromTemplate)
    env = {}
    rcf.config.mergeYamlData(env, config,  '.')
    rcf.config.mergeYamlData(env, secrets, '.')
    fileContents = template.render(env)
    with open(toPath, 'w') as toFile :
      toFile.write(fileContents)
  except Exception as err:
    print(f"Could not render the Jinja2 template")
    print(err)
    print("==========================================================")
    print(fromTemplate)
    print("==========================================================")
    print(yaml.dump(env))
    print("==========================================================")

def loadTasksFor(aRole=None) :
  if aRole :
    taskYaml = importlib.resources.read_text('rcf.roleResources.'+aRole, 'tasks.yaml')
  else :
    taskYaml = importlib.resources.read_text('rcf.roleResources', 'tasks.yaml')
  return yaml.safe_load(taskYaml)

def loadResourceFor(aRole, aResource) :
  return importlib.resources.read_text('rcf.roleResources.'+aRole, aResource)

def mergeVars(oldVars, newVars) :
  for aKey, aValue in newVars.items() :
    oldVars[aKey] = aValue.format(oldVars)
