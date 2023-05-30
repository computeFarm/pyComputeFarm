"""
This "module" provides the async methods required to access the TaskManager
using the ComputeFarm JSON RPC protocol.

This "module" is used by both the newTask and queryWorkers tools.
"""

import asyncio
import json
import sys
import yaml

async def tcpTMConnection(tmRequest) :
  try :
    reader, writer = await asyncio.open_connection(
      tmRequest['host'],
      tmRequest['port']
    )
  except ConnectionRefusedError :
    print("Could not connect to the taskManager")
    return (None, None)
  except Exception as err :
    print(f"Exception({err.__class__.__name__}): {str(err)}")
    return (None, None)
  return (reader, writer)

async def tcpTMSendRequest(tmRequest, reader, writer) :
  # send task request

  writer.write(json.dumps(tmRequest).encode())
  await writer.drain()
  writer.write(b"\n")
  await writer.drain()

async def tcpTMGetResult(reader, writer) :
  # read result
  resultJson = await reader.readuntil()
  retsult = {}
  if resultJson :
    result = json.loads(resultJson.decode())
  return result

async def tcpTMCloseConnection(reader, writer) :
  print("Closing the connection")
  writer.close()
  await writer.wait_closed()

async def tcpTMEchoResults(reader, writer, setWorkerReturnCode) :
  # echo any results

  moreToRead = True
  while moreToRead :
    print("Reading...")
    data = await reader.readuntil()
    aLine = data.decode().strip()
    # print(f'Received: [{aLine}]')
    if 'returncode' in aLine :
      workerJson = json.loads(aLine)
      if 'returncode' in workerJson :
        setWorkerReturnCode(workerJson['returncode'])
      if 'msg' in workerJson :
        print(workerJson['msg'])
      moreToRead = False
    if reader.at_eof()       : moreToRead = False

  await tcpTMCloseConnection(reader, writer)
