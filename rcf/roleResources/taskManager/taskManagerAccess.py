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
  except Exception as err :
    print("Could not connect to the taskManager")
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
  print("Closing the connection")
  tmSocket.shutdown(socket.SHUT_RDWR)
  tmSocket.close()

def tcpTMEchoResults(tmSocket, setWorkerReturnCode) :
  # echo any results

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
         setWorkerReturnCode(workerJson['returncode'])
       if 'msg' in workerJson :
         print(workerJson['msg'])
       moreToRead = False
    else : 
      print("Data is empty!")
      moreToRead = False

  tcpTMCloseConnection(tmSocket)
