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

#ToDo: research python method to execute function on failure just before exit...
# -- call lumen with "alarm" animation.

#ToDo: send animation to lumen on soft state interval.

urllib3.disable_warnings()

getStateIntervalDefault = 3600
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
    lumenPUT = requests.put('http://'+lumen+':9000/lumen', data=data)
    pdebug('response code: ' + str(lumenPUT.status_code) + ', response json: ' + lumenPUT.text )
  except:
    pdebug("failed to PUT animation to lumen")

def configGET(key):
  try:
    response = requests.get('http://'+config+':8443/badger/'+key, verify=False)
    return response.text
  except:
    return ""

def secretGET(key):
  try:
    response = requests.get('http://'+config+':8443/secret/'+key, verify=False)
    return response.text
  except:
    return ""


def getVehicle(vehicle):
  pdebug('start getVehicle')
  try:
    connection = teslajson.Connection(access_token=access_token, tesla_client='{"v1": {"id": "e4a9949fcfa04068f59abb5a658f2bac0a3428e4652315490b659d5ab3f35a9e", "secret": "c75f14bbadc8bee3a7594412c31416f8300256d7668ea7e6e7f06727bfb9d220", "baseurl": "https://owner-api.teslamotors.com", "api": "/api/1/"}}')
    vehicle = connection.vehicles[vehicle]
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
    state['vehicle'] = vehicle
    state['charge_state'] = vehicle.data_request('charge_state')
    state['climate_state'] = vehicle.data_request('climate_state')
    state['drive_state'] = vehicle.data_request('drive_state')
    state['gui_settings'] = vehicle.data_request('gui_settings')
    state['vehicle_state'] = vehicle.data_request('vehicle_state')
    state['vehicle_config'] = vehicle.data_request('vehicle_config')
    #state['mobile_enabled'] = vehicle.data_request('mobile_enabled')
    #state['nearby_charging_sites'] = vehicle.data_request('nearby_charging_sites')
  except:
    return state
  state['state'] = {}
  state['state']['distanceFromHome'] =  geodesic((state['drive_state']['latitude'],state['drive_state']['longitude']),tHome).ft
  if int(state['state']['distanceFromHome']) < int(tHomeRadiusFt):
    state['state']['isHome'] = True
  else:
    state['state']['isHome'] = False
  if int(state['charge_state']['ideal_battery_range']) >= int(tChargeRangeFull)-10:
    state['state']['isCharged'] = True
  else:
    state['state']['isCharged'] = False
  if int(state['charge_state']['ideal_battery_range']) <= int(tChargeRangeMedium):
    state['state']['shouldCharge'] = True
  else:
    state['state']['shouldCharge'] = False
  if int(state['charge_state']['ideal_battery_range']) <= int(tChargeRangeLow):
    state['state']['isLow'] = True
  else:
    state['state']['isLow'] = False
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
      pdebug('shift_state: ' + str(state['drive_state']['shift_state']) + ', speed: ' + str(state['drive_state']['speed']) + ', distance from home: ' + str(state['state']['distanceFromHome']) + ', range: ' + str(state['charge_state']['battery_range']) + ', charge rate: ' + str(state['charge_state']['charge_rate']))
      rangePercent = int(state['charge_state']['battery_range']) / int(tChargeRangeFull) * 100
      if state['state']['isHome'] == True and state['charge_state']['charging_state'] != 'Disconnected':
        pdebug('Car is home and plugged in!')
        lumenPUT('{"animation":"'+getConfig('eIHIP','fill')+'","rgbw":"'+getConfig('cIHIP','')+'","percent":'+str(rangePercent)+'}')
      elif state['state']['isHome'] == True and state['charge_state']['charging_state'] == 'Disconnected' and int(state['charge_state']['battery_range']) < int(tChargeRangeMedium):
        pdebug('car is home, not plugged in and below ' + tChargeRangeMedium + ' miles range')
        lumenPUT('{"animation":"'+getConfig('eIHNPBCRM','fill')+'","rgbw":"'+getConfig('cIHNPBCRM','')+'","percent":'+str(rangePercent)+'}')
      elif state['state']['isHome'] == True and state['charge_state']['charging_state'] == 'Disconnected':
        pdebug('Warning car is home but not plugged in!')
        lumenPUT('{"animation":"'+getConfig('eIHNP','fill')+'","rgbw":"'+getConfig('cIHNP','')+'","percent":'+str(rangePercent)+'}')
      elif state['state']['isHome'] == False:
        pdebug('Car is not at home')
        lumenPUT('{"animation":"'+getConfig('eNH','rainbow')+'","rgbw":"'+getConfig('cNH','')+'","percent":'+str(rangePercent)+'}')
      elif state['drive_state']['shift_state'] != None:
        lumenPUT('{"animation":"rainbow","percent":'+str(rangePercent)+'}')
    currentStateKey = 'ts_'+str(int(time.time()))
    try:
      dataPUT = requests.put('http://'+config+':8443/badger/'+currentStateKey, data=json.dumps(state), verify=False)
      pdebug("PUT currentState response code: " + str(dataPUT.status_code))
      dataPUT = requests.put('http://'+config+':8443/badger/currentStateKey',currentStateKey,verify=False)
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
tToken = secretGET('tToken')
access_token = json.loads(tToken)['access_token']
tChargeRangeFull = getConfig('tChargeRangeFull','270')
tChargeRangeMedium = getConfig('tChargeRangeMedium','100')
tChargeRangeLow = getConfig('tChargeRangeLow','30')
tVehicle = int(getConfig('tVehicle','0'))
getStateInterval = int(getConfig('tGetStateInterval','3600'))
softStateInterval = int(getConfig('tSoftStateInterval','300'))
lastSoftStateInterval = float(getConfig('lastSoftStateInterval','0'))
if lastSoftStateInterval == 0:
  lastSoftStateInterval = time.time()
  pdebug('lastSoftStateInterval set to now:' + str(lastSoftStateInterval))
else:
  pdebug('lastSoftStateInterval restore from badger:'+str(lastSoftStateInterval))

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

  #Todo: keep check interval short for 1 full cycle before going back to default.
  #Todo: current (5 minute) default for soft check may be too short.. ?10 mintes? -- many be dynamic depending on battery %.

queryNext = False
while True:
  if int(time.time()) - int(lastSoftStateInterval) > int(softStateInterval):
    softStateInterval = int(getConfig('tSoftStateInterval','300'))
    lastSoftStateInterval = time.time()
    try:
      dataPUT = requests.put('http://'+config+':8443/badger/lastSoftStateInterval',str(time.time()),verify=False)
      pdebug("PUT lastSoftStateInterval response code: " + str(dataPUT.status_code))
    except:
      pdebug('failed to store lastSoftStateInterval')
    vehicle = getVehicle(tVehicle)
    pdebug('soft check state: ' + vehicle['state'])
    if vehicle['state'] == 'online':
      queryNext = True
    else:
      queryNext = False
      pdebug('  next soft state check: ' + str(datetime.datetime.now() + datetime.timedelta(seconds=softStateInterval)) + ' (' + str(softStateInterval) + ')')
  if int(time.time()) - int(state['data_state']['timestamp']) > getStateInterval:
    vehicle = getVehicle(tVehicle)
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
