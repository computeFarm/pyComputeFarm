"""
This "module" provides the (socket) methods required to access the TaskManager
using the ComputeFarm JSON RPC protocol.

This "module" is used by both the newTask and queryWorkers tools.
"""

import json
import socket
import sys
import yaml

def tcpTMConnection(tmRequest) :
  try :
    tmSocket = socket.create_connection((
      tmRequest['host'],
      tmRequest['port']
    ))
    print(f"Connected to the taskManager on {tmRequest['host']}:{tmRequest['port']}")
  except ConnectionRefusedError as err :
    print(f"Could not connect to the taskManager on {tmRequest['host']}:{tmRequest['port']}")
    return None
  except Exception as err :
    print(f"Exception({err.__class__.__name__}): {str(err)}")
    return None
  return tmSocket

def tcpTMSentRequest(tmRequest, tmSocket) :
  # send task request
  try :
    tmSocket.sendall(json.dumps(tmRequest).encode() + b"\n")
  except Exception as err :
    print("Lost connection to the taskManager while sending a request")
    print(f"Exception({err.__class__.__name__}): {str(err)}")
    return False
  return True

def tcpTMGetResult(tmSocket) :
  # read result
  result = {}
  resultJson = None
  try : 
    resultJson = tmSocket.recv(4096)
  except Exception as err :
    print("Lost connection to the taskManager while getting a result")
    print(f"Exception({err.__class__.__name__}): {str(err)}")
  if resultJson :
    result = json.loads(resultJson.decode())
  return result

def tcpTMCloseConnection(tmSocket) :
  print("Closing the connection to the taskManager")
  tmSocket.shutdown(socket.SHUT_RDWR)
  tmSocket.close()

def tcpTMCollectResults(tmSocket, msgArray) :
  
  returnCode = 1
  moreToRead = True
  while moreToRead :
    print("Reading...")
    data = None
    try : 
      data = tmSocket.recv(4096)
    except Exception as err :
      print("Lost connection to the taskManager")
      print(f"Exception({err.__class__.__name__}): {str(err)}")
    if data :
     aLine = data.decode().strip()
     #print(f'Received: [{aLine}]')
     if 'returncode' in aLine :
       workerJson = json.loads(aLine)
       if 'returncode' in workerJson :
         returnCode = workerJson['returncode']
         moreToRead = False
       if 'msg' in workerJson :
        if msgArray : msgArray.append(workerJson['msg'])
        else        : print(workerJson['msg'])
    else : 
      print("Data is empty!")
      moreToRead = False

  tcpTMCloseConnection(tmSocket)
  return returnCode

def compileActionScript(someAliases, someEnvs, someActions) :
  """
  Create a (unix) shell script which can run the actions specified by the
  `someActions` (list of lists or strings) parameter using (unix shell)
  environment variables specified in the `someEnvs` (list of dicts) parameter as
  well as the aliases specified in the `someAliases` (dict) parameter.
  """

  # consider using os.path.expanduser and our own normalizePath

  actionScript = []
  actionScript.append("#!/bin/sh")

  actionScript.append("# export the aliases...")
  if isinstance(someAliases, dict) :
    for aKey, aValue in someAliases.items() :
      actionScript.append(f"alias {aKey}=\"{aValue}\"")

  actionScript.append("# export the environment...")
  if isinstance(someEnvs, list) :
    for anEnv in someEnvs :
      if isinstance(anEnv, dict) :
        for aKey, aValue in anEnv.items() :
          actionScript.append(f"export {aKey}=\"{aValue}\"")

  actionScript.append("# now run the actions...")
  for anAction in someActions :
    if isinstance(anAction, str) :
      actionScript.append(anAction)
    elif isinstance(anAction, list) :
      actionScript.append(" ".join(anAction))

  return "\n\n".join(actionScript)
