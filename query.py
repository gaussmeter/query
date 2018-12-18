#!/usr/bin/python3
import sys
import signal
import teslajson
import time
import datetime
import pprint
import json
from geopy.distance import geodesic

home = open('/var/run/secrets/home', 'r').read().strip()
maxDistanceFt = 100
username = open('/var/run/secrets/email', 'r').read().strip()
password = open('/var/run/secrets/password', 'r').read().strip() 
getStateIntervalDefault = 3600
getStateInterval = getStateIntervalDefault 
getStateIntervalActive = 5 
getStateIntervalOnline = 900 
getStateIntervalOnline = 1200 
getStateIntervalOnline = getStateIntervalDefault 
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

# soft check every 15 minutes if car is online, then get state.  

while True:
  if int(time.time()) - int(state['data_state']['timestamp'])  > getStateInterval:
    vehicle = getVehicle()
    if vehicle['state'] != 'failed':
      state = getState(vehicle)
      if state['data_state']['isGood'] == True:
        #pprint.pprint(state, indent=2)
        pdebug('shift_state: ' + str(state['drive_state']['shift_state']) + ' speed: ' + str(state['drive_state']['speed']) + ' distance from home: ' + str(state['vehicle_state']['distanceFromHome']))
        if state['vehicle_state']['isHome'] == True and state['charge_state']['charging_state'] != 'Disconnected':
          pdebug('Car is home and plugged in!')
        if state['vehicle_state']['isHome'] == True and state['charge_state']['charging_state'] == 'Disconnected':
          pdebug('Warning car is home but not plugged in!')
        if state['vehicle_state']['isHome'] == False:
          pdebug('Car is not at home')
        if state['drive_state']['shift_state'] != None:
          getStateInterval = getStateIntervalActive 
        else:
          getStateInterval = getStateIntervalOnline 
    pdebug('next check: ' + str(datetime.datetime.now() + datetime.timedelta(seconds=getStateInterval)) + ' (' + str(getStateInterval) + ')')
  time.sleep(.5)
