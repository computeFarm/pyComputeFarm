
import jinja2

import rcf.config

def jinjaFile(fromPath, toPath, config, secrets) :
  try:
    with open(fromPath, "r") as fromFile :
      fromTemplate = fromFile.read()
    template = jinja2.Template(fromTemplate)
    env = {}
    rcf.config.mergeYamlData(env, config,  '.')
    rcf.config.mergeYamlData(env, secrets, '.')
    fileContents = template.render(env)
    with open(toPath, 'w') as toFile :
      toFile.write(fileContents)
  except Exception as err:
    print(f"Could not render the Jinja2 template [{fromPath}]")
    print(err)

