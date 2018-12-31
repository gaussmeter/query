#!/usr/bin/python3
import sys
import signal
import teslajson
import time
import datetime
import pprint
import json
import requests
import urllib3
from geopy.distance import geodesic

urllib3.disable_warnings()

maxDistanceFt = 100
getStateIntervalDefault = 3600
getStateInterval = getStateIntervalDefault
getStateIntervalActive = 5 
getStateIntervalOnline = 900 
getStateIntervalOnline = 1200 
getStateIntervalOnline = getStateIntervalDefault
loginfailloop = 90
debugEnabled = True

def signal_handler(sig, frame):
  pdebug('You pressed Ctrl+C!')
  sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def pdebug(message):
  if debugEnabled == True:
    print(str(datetime.datetime.now()) + ' ' + message)

def initializeState():
  state = {}
  state['data_state'] = {}
  state['data_state']['timestamp'] = 0
  state['data_state']['isGood'] = False
  return state

def lumenPUT(data):
  try:
    lumenPUT = requests.put('http://lumen:9000/lumen', data=data)
    pdebug('response code: ' + str(lumenPUT.status_code) + ', response json: ' + lumenPUT.text )
  except:
    pdebug("failed to PUT animation to lumen")


def getVehicle():
  pdebug('start getVehicle')
  try:
    connection = teslajson.Connection(username, password, tesla_client='{"v1": {"id": "e4a9949fcfa04068f59abb5a658f2bac0a3428e4652315490b659d5ab3f35a9e", "secret": "c75f14bbadc8bee3a7594412c31416f8300256d7668ea7e6e7f06727bfb9d220", "baseurl": "https://owner-api.teslamotors.com", "api": "/api/1/"}}')
    return connection.vehicles[0]
  except: 
    return {'state' : 'failed'}

def getState(vehicle):
  pdebug('start getState')
  state = initializeState() 
  vehicleState = vehicle['state']
  while True:
    pdebug(vehicleState)
    if vehicleState != 'online':
      time.sleep(5)
      try: 
        vehicleState = vehicle.wake_up()['response']['state']
      except:
        return state
    else: 
      break
  try:
    state['drive_state'] = vehicle.data_request('drive_state')
    state['climate_state'] = vehicle.data_request('climate_state')
    state['charge_state'] = vehicle.data_request('charge_state')
  except:
    return state
  state['vehicle_state'] = {}
  state['vehicle_state']['distanceFromHome'] =  geodesic((state['drive_state']['latitude'],state['drive_state']['longitude']),home).ft 
  if state['vehicle_state']['distanceFromHome'] < maxDistanceFt:
    state['vehicle_state']['isHome'] = True
  else:
    state['vehicle_state']['isHome'] = False 
  state['data_state']['timestamp'] = int(time.time())
  state['data_state']['isGood'] = True 
  return state

state = initializeState()

try:
  home = open('/var/run/secrets/home', 'r').read().strip()
  pdebug('note: home = ' + home)
except:
  home = '37.4919392,-121.9469367'
  pdebug('warning: home = ' + home)

try:
  username = open('/var/run/secrets/email', 'r').read().strip()
  pdebug('note: username = ' + username)
except:
  pdebug('warning: username = None')
  username = None

try:
  password = open('/var/run/secrets/password', 'r').read().strip()
  pdebug('note: password = [redacted]')
except:
  pdebug('warning: password = None')
  password = None

try:
  minimumRange = open('/var/run/secrets/minrange', 'r').read().strip()
except:
  minimumRange = 100
  pdebug('defaulting: minimumRange = ' + str(minimumRange))

# Todo: soft check every 15 minutes if car is online, then get state.

while True:
  if int(time.time()) - int(state['data_state']['timestamp'])  > getStateInterval:
    vehicle = getVehicle()
    if vehicle['state'] != 'failed':
      state = getState(vehicle)
      if state['data_state']['isGood'] == True:
        #pprint.pprint(state, indent=2)
        pdebug('shift_state: ' + str(state['drive_state']['shift_state']) + ', speed: ' + str(state['drive_state']['speed']) + ', distance from home: ' + str(state['vehicle_state']['distanceFromHome']) + ', range: ' + str(state['charge_state']['battery_range']) )
        if state['vehicle_state']['isHome'] == True and state['charge_state']['charging_state'] != 'Disconnected':
          pdebug('Car is home and plugged in!')
          lumenPUT('{"animation":"fill","g":255}')
        elif state['vehicle_state']['isHome'] == True and state['charge_state']['charging_state'] == 'Disconnected' and state['charge_state']['battery_range'] < minimumRange:
          pdebug('car is home, not plugged in and below ' + minimumRange + ' miles range')
          lumenPUT('{"animation":"fill","r":255}')
        elif state['vehicle_state']['isHome'] == True and state['charge_state']['charging_state'] == 'Disconnected':
          pdebug('Warning car is home but not plugged in!')
          lumenPUT('{"animation":"fill","r":255,"g":255}')
        elif state['vehicle_state']['isHome'] == False:
          pdebug('Car is not at home')
          lumenPUT('{"animation":"rainbow"}')
        elif state['drive_state']['shift_state'] != None:
          getStateInterval = getStateIntervalActive
          lumenPUT('{"animation":"rainbow"}')
        else:
          getStateInterval = getStateIntervalOnline
      currentStateKey = datetime.datetime.now().isoformat()
      try:
        dataPUT = requests.put('https://config:8443/badger/'+currentStateKey, data=json.dumps(state), verify=False)
        pdebug("PUT currentState response code: " + str(dataPUT.status_code))
        dataPUT = requests.put('https://config:8443/badger/currentStateKey',currentStateKey,verify=False)
        pdebug("PUT currentStateKey response code: " + str(dataPUT.status_code))
      except:
        pdebug("failed to PUT currentState and currentStateKey")
    else:
      pdebug('login failed, sleeping for a while')
      for i in range(loginfailloop):
        lumenPUT('{"animation":"fill","r":255}')
        time.sleep(1)
        lumenPUT('{"animation":"fill"}')
        time.sleep(1)
    pdebug('next check: ' + str(datetime.datetime.now() + datetime.timedelta(seconds=getStateInterval)) + ' (' + str(getStateInterval) + ')')
  time.sleep(.5)
