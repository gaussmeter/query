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
import os
from geopy.distance import geodesic

urllib3.disable_warnings()

getStateIntervalDefault = 3600
getStateIntervalActive = 5
getStateIntervalOnline = 900 
getStateIntervalOnline = 1200 
getStateIntervalOnline = getStateIntervalDefault
loginfailloop = 90
debugEnabled = True
lastSoftStateInterval = time.time()


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
    lumenPUT = requests.put('http://'+lumen+':9000/lumen', data=data)
    pdebug('response code: ' + str(lumenPUT.status_code) + ', response json: ' + lumenPUT.text )
  except:
    pdebug("failed to PUT animation to lumen")

def configGET(key):
  try:
    response = requests.get('https://'+config+':8443/badger/'+key, verify=False)
    return response.text
  except:
    return ""


def getVehicle():
  pdebug('start getVehicle')
  try:
    connection = teslajson.Connection(tEmailAdr, tPassword, tesla_client='{"v1": {"id": "e4a9949fcfa04068f59abb5a658f2bac0a3428e4652315490b659d5ab3f35a9e", "secret": "c75f14bbadc8bee3a7594412c31416f8300256d7668ea7e6e7f06727bfb9d220", "baseurl": "https://owner-api.teslamotors.com", "api": "/api/1/"}}')
    vehicle = connection.vehicles[0]
    #pprint.pprint(vehicle, indent=2)
    return vehicle
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
  state['vehicle_state']['distanceFromHome'] =  geodesic((state['drive_state']['latitude'],state['drive_state']['longitude']),tHome).ft
  if int(state['vehicle_state']['distanceFromHome']) < int(tHomeRadiusFt):
    state['vehicle_state']['isHome'] = True
  else:
    state['vehicle_state']['isHome'] = False
  if int(state['charge_state']['ideal_battery_range']) >= int(tChargeRangeFull)-10:
    state['vehicle_state']['isCharged'] = True
  else:
    state['vehicle_state']['isCharged'] = False
  if int(state['charge_state']['ideal_battery_range']) <= int(tChargeRangeMedium):
    state['vehicle_state']['shouldCharge'] = True
  else:
    state['vehicle_state']['shouldCharge'] = False
  if int(state['charge_state']['ideal_battery_range']) <= int(tChargeRangeLow):
    state['vehicle_state']['isLow'] = True
  else:
    state['vehicle_state']['isLow'] = False
  state['data_state']['timestamp'] = int(time.time())
  state['data_state']['isGood'] = True
  return state

if os.environ.get('LUMEN') != None:
  lumen = os.environ.get('LUMEN')
else:
  lumen = 'lumen'
if os.environ.get('CONFIG') != None:
  config = os.environ.get('CONFIG')
else:
  config = 'config'

pdebug('lumen server: ' + lumen)
pdebug('config server: ' + config)

def getConfig(key, defaultVal):
  try:
    val = open('/var/run/config/' + key, 'r').read().strip()
    pdebug('note: ' + key + ' = ' + val)
    return val
  except:
    val = configGET(key)
    pdebug('from configGET: ' + key + ' = ' + val)
    if val == "":
      val = defaultVal
      pdebug('defaulted: ' + key + ' = ' + val)
    return val

def query(vehicle):
  if vehicle['state'] != 'failed':
    state = getState(vehicle)
    if state['data_state']['isGood'] == True:
      #pprint.pprint(state, indent=2)
      pdebug('shift_state: ' + str(state['drive_state']['shift_state']) + ', speed: ' + str(state['drive_state']['speed']) + ', distance from home: ' + str(state['vehicle_state']['distanceFromHome']) + ', range: ' + str(state['charge_state']['battery_range']) )
      if state['vehicle_state']['isHome'] == True and state['charge_state']['charging_state'] != 'Disconnected':
        pdebug('Car is home and plugged in!')
        lumenPUT('{"animation":"'+getConfig('eIHIP','fill')+'","rgbw":"'+getConfig('cIHIP','')+'"}')
      elif state['vehicle_state']['isHome'] == True and state['charge_state']['charging_state'] == 'Disconnected' and int(state['charge_state']['battery_range']) < int(tChargeRangeMedium):
        pdebug('car is home, not plugged in and below ' + tChargeRangeMedium + ' miles range')
        lumenPUT('{"animation":"'+getConfig('eIHNPBCRM','fill')+'","rgbw":"'+getConfig('cIHNPBCRM','')+'"}')
      elif state['vehicle_state']['isHome'] == True and state['charge_state']['charging_state'] == 'Disconnected':
        pdebug('Warning car is home but not plugged in!')
        lumenPUT('{"animation":"'+getConfig('eIHNP','fill')+'","rgbw":"'+getConfig('cIHNP','')+'"}')
      elif state['vehicle_state']['isHome'] == False:
        pdebug('Car is not at home')
        lumenPUT('{"animation":"'+getConfig('eNH','rainbow')+'","rgbw":"'+getConfig('cNH','')+'"}')
      elif state['drive_state']['shift_state'] != None:
        lumenPUT('{"animation":"rainbow"}')
    currentStateKey = datetime.datetime.now().isoformat()
    try:
      dataPUT = requests.put('https://'+config+':8443/badger/'+currentStateKey, data=json.dumps(state), verify=False)
      pdebug("PUT currentState response code: " + str(dataPUT.status_code))
      dataPUT = requests.put('https://'+config+':8443/badger/currentStateKey',currentStateKey,verify=False)
      pdebug("PUT currentStateKey response code: " + str(dataPUT.status_code))
    except:
      pdebug("failed to PUT currentState and/or currentStateKey")
  else:
    pdebug('login failed, sleeping for a while')
    for i in range(loginfailloop):
      lumenPUT('{"animation":"fill","r":255}')
      time.sleep(1)
      lumenPUT('{"animation":"fill"}')
      time.sleep(1)
  return state

tHome = getConfig('tHome','37.4919392,-121.9469367')
tHomeRadiusFt = getConfig('tHomeRadiusFt','100')
tWork = getConfig('tWork','37.4919392,-121.9469367')
tWorkRadiusFt = getConfig('tWorkRadiusFt','1000')
tEmailAdr = getConfig('tEmailAdr',"")
tChargeRangeFull = getConfig('tChargeRangeFull','270')
tChargeRangeMedium = getConfig('tChargeRangeMedium','100')
tChargeRangeLow = getConfig('tChargeRangeLow','30')
getStateInterval = int(getConfig('tGetStateInterval','3600'))
softStateInterval = int(getConfig('tSoftStateInterval','300'))

try:
  state = json.loads(getConfig(getConfig('currentStateKey',''),''))
  pdebug('state recovered... ')
except:
  state = initializeState()

try:
  tPassword = open('/var/run/secrets/tPassword', 'r').read().strip()
  pdebug('note: tPassword = [redacted]')
except:
  pdebug('warning: tPassword = None')
  tPassword = None

# Todo: fix check interval when driving and when charging. ?30 seconds?

queryNext = False
firstSoftCheck = True
while True:
  if int(time.time()) - int(lastSoftStateInterval) > int(softStateInterval) or firstSoftCheck == True:
    firstSoftCheck = False
    lastSoftStateInterval = time.time()
    vehicle = getVehicle()
    pdebug('soft check state: ' + vehicle['state'])
    if vehicle['state'] == 'online':
      queryNext = True
    else:
      queryNext = False
      pdebug('  next soft state check: ' + str(datetime.datetime.now() + datetime.timedelta(seconds=softStateInterval)) + ' (' + str(softStateInterval) + ')')
  if int(time.time()) - int(state['data_state']['timestamp']) > getStateInterval:
    vehicle = getVehicle()
    queryNext = True
  if queryNext == True:
    state = query(vehicle)
    if state['drive_state']['shift_state'] != None:
      getStateInterval = int(getConfig('tGetStateIntervalDriving','30'))
    elif state['charge_state']['charge_rate'] > 0:
      getStateInterval = int(getConfig('tGetStateIntervalCharging','60'))
    else:
      getStateInterval = int(getConfig('tGetStateInterval','3600'))
    queryNext = False
    lastSoftStateInterval = time.time()
    pdebug('next hard vehicle query: ' + str(datetime.datetime.now() + datetime.timedelta(seconds=getStateInterval)) + ' (' + str(getStateInterval) + ')')
    pdebug('  next soft state check: ' + str(datetime.datetime.now() + datetime.timedelta(seconds=softStateInterval)) + ' (' + str(softStateInterval) + ')')
  time.sleep(.5)
