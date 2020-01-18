#!/usr/bin/python
# rover control
# version: 0.8
# modify date: 18/01/2019
# 
# 0.8
# 1. adapted for vehicle controlled with stepper motor for direction
# 2. pi-blaster pwm parameter adjustment: sample_US 5 (default = 10
#    cycle_time_us 1000 (default 10000)
#    PWM = 1000hz
# 3. define different maxdelta for x & y axis
#
# 0.7
# 1. add led light control via relay switch: momentary type
# 2. remove RGB led light control
#
# 0.6
# 1. add speed control toggled by topic rover/speedcontrol
#    1: unrestrictded speed
#    0: speed limited: deltaY limited
#    
# 0.5
# 1. add display public ip / local ip & publish to mqtt
# 2. logout message to mqtt sysmsg topic
# 3. able to disconnect from openvpn
# 4. enable exception/error handling when getting public ip even when 
#    there is no internet access
#
# 0.4
# 1. add lipo voltage check
#    display warning message via channel rover/voltage
#    stop program if vmin reached
# 2. need Adafruit_ADS1x15 module installed
#    sudo pip install adafruit-ads1x15
#    sudo apt-get install -y i2c-tools
#    
# 0.3
# 1. remove magnetometer module codes
# 2. mqtt server info updated
# 3. motor driver connection
#    R_EN & L_EN connect to 3.3v : always enabled
#    control via PWM pins
# 0.2
# 1. add magnetometer MAG3110 module
# 2. adjust motor (Rt/Lt) according to heading info
# 3. obtain heading info from MQTT topic: heading
# 0.1
# 1. monitor trigger from mqtt server
# 2. activate motor from trigger
#
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt
import time
import datetime
import os
import subprocess
import logging
import logging.handlers
import socket
import Adafruit_ADS1x15
import socket
from json import load
from urllib2 import urlopen

def killvpn():
  logout("disconnect from openvpn server")
  CMD("sudo killall openvpn")

def connectvpn():
  logout("connect openvpn server")
  CMD("sudo openvpn wilson.ovpn")

def getPrivateIP():
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  try:
    # doesn't even have to be reachable
    s.connect(('10.255.255.255', 1))
    IP = s.getsockname()[0]
  except:
    IP = '127.0.0.1'
  finally:
    s.close()
  client.publish(privateip_tp, IP)
  return IP

def getPublicIP():
  try:
    IP = load(urlopen('https://api.ipify.org/?format=json'))['ip']
  except:
    IP = '0.0.0.0'
  client.publish(publicip_tp, IP)
  return IP

def connectMQTT():
  #disable this for device connecting to another MQTT server
  #rlog2.info("connecting to mqtt server")
  #global client
  run_main = False
  run_flag = True
  while run_flag:
    #while not client.connected_flag and client.retry_count < 3:
    while not client.connected_flag:
      count = 0 
      run_main = False
      try:
        print("connecting ", mqttserver)
        client.connect_async(mqttserver, mqttport, keepalivetime)
        break
      except:
        print("connection attempt failed will retry")
        client.retry_count+=1
        if client.retry_count > 3:
          run_flag = False
    if not run_main:   
      client.loop_start()
      while True:
        if client.connected_flag: #wait for connack
          client.retry_count = 0 #reset counter
          run_main = True
          break
        #if count > 6 or client.bad_connection_flag: #don't wait forever
        if client.bad_connection_flag: # attempt reconnect forever
          client.loop_stop() #stop loop
          client.retry_count+=1
          #if client.retry_count > 3:
          #  run_flag = False
          break #break from while loop

          time.sleep(1)
          count+=1

    if run_main:
      #Do main loop
      break

def on_connect(client, data, flags, rc):
  # connection event
  if rc == 0:
    msg = "connected to MQTT server " + mqttserver + " on port " + str(mqttport)
    logoutput(msg)
    client.connected_flag = True #Flag to indicate success
    # subscribe to topic
    client.subscribe("rover/deltaX", qos = 2)
    client.subscribe("rover/deltaY", qos = 2)
    client.subscribe("rover/killvpn", qos = 2)
    client.subscribe("rover/connectvpn", qos = 2)
    client.subscribe(speedcontrol_tp, qos = 2)
    client.subscribe(light_tp, qos = 2)
  else:
    msg = "Bad mqtt connection; returned code = " + str(rc)
    logoutput(msg)
    client.bad_connection_flag = True

def on_disconnect(client, userdata, flags, rc=0):
  msg = "Disconnected from mqtt server; return code = " + str(rc)
  logoutput(msg)
  client.conncted_flag = False

def on_subscribe(client, userdata, mid, gqos):
  # subscription event
  logoutput('Subscribed: ' + str(mid))

def on_message(client, obj, msg):
  global deltaX
  global deltaY
  print(msg.topic + " : " + str(msg.payload))
  if msg.topic == "rover/deltaX":
    deltaX = int(msg.payload)
    checkDirection()
  
  if msg.topic == "rover/deltaY":
    deltaY = int(msg.payload)
    checkDirection()

  if msg.topic == "rover/killvpn":
    logoutput("kill vpn")
    CMD("sudo killall openvpn")
    CMD("sudo ip link delete tun0")

  if msg.topic == "rover/connectvpn":
    logoutput("connect openvpn")
    CMD("sudo openvpn wilson.ovpn")

  if msg.topic == speedcontrol_tp:
    if msg.payload == "0":
      speedcontrol = 0
      logoutput("speed restricted")
      speedmodifer = 0.6
    if msg.payload == "1":
      speedcontrol = 1
      logoutput("speed unrestricted")
      speedmodifer = 1.0

  if msg.topic == light_tp:
    if msg.payload ==  "1":
      GPIO.output(light_pin, True)
      time.sleep(0.2)
      GPIO.output(light_pin, False)
      logoutput("light switch pressed")
      client.publish(light_tp, "0")
    
def checkDirection():
  # check deltaX & deltaY + adjust motor controller
  global deltaX
  global deltaY
  global lastdeltaX
  global lastdeltaY
  reduction = 0.0
  #print maxdelta
  if (abs(deltaX) > maxdeltaX):
    if (deltaX > 0):
      deltaX = maxdeltaX
    else:
      deltaX = -maxdeltaX

  if (abs(deltaY) > maxdeltaY):
    if (deltaY > 0):
      deltaY = maxdeltaY
    else:
      deltaY = -maxdeltaY

  if (deltaX > 0) and (deltaX < 10):
    deltaX = 0
  
  if (deltaX < 0) and (deltaX > -10):
    deltaX = 0

  if (deltaX >= 0):
    if (deltaY >= 0):
      # backward + right
      print("backward + right")
      #reduction = deltaY / maxdelta * (1 - (deltaX / maxdelta))
      #print reduction
      #reduction = deltaY / maxdelta 
      #print reduction
      commands = PiBlasterCmd(LPWM1, abs(deltaX) / maxdeltaX)
      commands = commands + ' | ' + PiBlasterCmd(RPWM1, 0)
      commands = commands + ' | ' + PiBlasterCmd(LPWM2, abs(deltaY) / maxdeltaY)
      commands = commands + ' | ' + PiBlasterCmd(RPWM2, 0)
    else:
      # forward + right
      print("forward + right")
      print("NOT stopped by forward ultrasound")
      commands = PiBlasterCmd(LPWM1, abs(deltaX) / maxdeltaX)
      commands = commands + ' | ' + PiBlasterCmd(RPWM1, 0)
      commands = commands + ' | ' + PiBlasterCmd(LPWM2, 0)
      commands = commands + ' | ' + PiBlasterCmd(RPWM2, abs(deltaY) / maxdeltaY)

      #commands = PiBlasterCmd(LPWM1, abs(deltaY) / maxdelta * speedmodifer *  (1 - (deltaX / maxdelta)))
      #commands = commands + ' | ' + PiBlasterCmd(LPWM2, abs(deltaY) / maxdelta * speedmodifer)
      
  else:
    if (deltaY >= 0):
      # backward + left
      print("backward + left")
      commands = PiBlasterCmd(LPWM1, 0)
      commands = commands + ' | ' + PiBlasterCmd(RPWM1, abs(deltaX) / maxdeltaX)
      commands = commands + ' | ' + PiBlasterCmd(LPWM2, abs(deltaY) / maxdeltaY)
      commands = commands + ' | ' + PiBlasterCmd(RPWM2, 0)

    else:
      # forward + left
      print("forward + left")
      commands = PiBlasterCmd(LPWM1, 0)
      commands = commands + ' | ' + PiBlasterCmd(RPWM1, abs(deltaX) / maxdeltaX)
      commands = commands + ' | ' + PiBlasterCmd(LPWM2, 0)
      commands = commands + ' | ' + PiBlasterCmd(RPWM2, abs(deltaY) / maxdeltaY)
  #print(commands)
  os.system(commands)

def CMD(cmd):
  p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=False) 
  return (p.stdin, p.stdout, p.stderr) 

def setuplogger():
  # assign logging
  #logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',filename="/var/log/pir.log",level=logging.DEBUG)
  global rlog, rlog2, sysloghandler, filehandler, formatter
  rlog = logging.getLogger(devicename)
  rlog.setLevel(logging.DEBUG)
  sysloghandler = logging.handlers.SysLogHandler(address = (sysloghost,syslogport))
  filehandler = logging.FileHandler(logfile)
  formatter = logging.Formatter("%(asctime)s %(hostname)s: %(message)s", datefmt='%m/%d/%Y %I:%M:%S %p')
  sysloghandler.setFormatter(formatter)
  filehandler.setFormatter(formatter)
  rlog.addHandler(sysloghandler)
  rlog.addHandler(filehandler)
  rlog2 = logging.LoggerAdapter(rlog, {'hostname': hostname})
  rlog2.debug("test")

def logoutput(msg):
  global rlog2
  print(msg)
  rlog2.debug(msg)
  client.publish(sysmsg_tp, msg)

def reloadMQTT():
  #global client 
  #client = mqtt.Client(client_id = mqttuser)
  client.connected_flag = False
  client.bad_connection_flag = False
  client.retry_count = 0
  client.username_pw_set(mqttuser, mqttpass)
  client.on_message = on_message
  client.on_connect = on_connect
  client.on_subscribe = on_subscribe
  client.on_disconnect = on_disconnect

  client.disconnect()
  connectMQTT()

def PiBlasterCmd(pin, pos):
  return 'echo "' + str(pin) + '=' + str(pos) +'" > /dev/pi-blaster'

def checkfultrasound(trigpin, echopin, force):
  global lastfultrasound
  checkfultrasound = 20
  return
  needtocheck = 0
  if (force == 1):
    needtocheck = 1
  else:
    if (time.time() - lastfultrasound >= ultrasoundinterval):
      needtocheck = 1

  if (needtocheck == 1):
    print ("check forward ultrasound")
    checkfultrasound = distance(trigpin, echopin)
    lastfultrasound = time.time()
    return checkfultrasound

def checkbultrasound(trigpin, echopin, force):
  global lastbultrasound
  needtocheck = 0
  if (force == 1):
    needtocheck = 1
  else:
    if (time.time() - lastbultrasound >= ultrasoundinterval):
      needtocheck = 1

  if (needtocheck == 1):
    checkbultrasound = distance(trigpin, echopin)
    lastbultrasound = time.time()
    return checkbultrasound

def distance(trigpin, echopin):
  # active + check u/s sensor
  GPIO.output(trigpin, False)
  time.sleep(0.00001)

  # set Trigger to HIGH
  GPIO.output(trigpin, True)
 
  # set Trigger after 0.01ms to LOW
  time.sleep(0.0001)
  GPIO.output(trigpin, False)

  # save StartTime
  while GPIO.input(echopin) == 0:
    StartTime = time.time()
 
  # save time of arrival
  while GPIO.input(echopin) == 1:
    StopTime = time.time()
 
  # time difference between start and arrival
  TimeElapsed = StopTime - StartTime
  # multiply with the sonic speed (34300 cm/s)
  # and divide by 2, because there and back
  distance = TimeElapsed / 0.000058

  return distance

def checkbattery(ADCchannel, GAIN):
  global lastbatterycheck
  ADCvalue = adc.read_adc(ADCchannel, gain=GAIN)
  voltage = ADCvalue / 32767.0 * 4.096
  vin = (voltage * (R1 + R2) /  R2) - variance
  vperc = (vin - vmin) / (vmax - vmin) * 100
  stop = 0
  voltageStr = "voltage: " + "{:.2f}".format(vin) + " (" + "{:.1f}".format(vperc) + "%)"
  print(voltageStr)
  client.publish(voltage_tp, voltageStr)
  lastbatterycheck = time.time()
  if (vin <= 0):
    return

  if (vin < valarm):
    if (vin <= vmin):
      msg = "minimum voltage reached for lipo battery @ " + "{:.3f}".format(vin) + " : program will terminate"
      stop = 1
    else:
      msg = "alarm voltage reached @ " + "{:.3f}".format(vin) + " : ready to remove battery"
    logoutput(msg)
    return stop

# device topics
hostname = socket.gethostname()
devicename = hostname
sitename = "wilson"
location = "rover"
masterdevicename = "rover"
basestr = masterdevicename
sysmsg_tp = basestr + "/sysmsg"
sysmsgtime_tp = basestr + "/sysmsgtime"
trigger_tp = basestr + "/trigger"  # receiving messages
motion_tp = basestr + "/motion"
restart_tp = basestr + "/restart"
stop_tp = basestr + "/stop"
armdisarm_tp = "archer/armdisarm"
pir_tp = basestr + "/pir"
voltage_tp = basestr + "/voltage"
publicip_tp = basestr + "/publicip"
privateip_tp = basestr + "/privateip"
speedcontrol_tp = basestr + "/speedcontrol"
light_tp = basestr + "/light"

# mqtt variables
# device credentials
device_id = hostname      # * set your device id (will be the MQTT client username)
device_secret = ''        # * set your device secret (will be the MQTT client password)
mqttserver = "220.233.63.90"
mqttport = 8883
keepalivetime = 60
userprefix = "core-"
mqttuser = userprefix + devicename
mqttpass = "wree1234"
sysloghost = mqttserver
syslogport = 515
logfile = "/home/core/pir.log"

# pin variables BCM
# direction control
RPWM1 = 17  # right
LPWM1 = 18  # left
# forward/backward control
RPWM2 = 22  # forward
LPWM2 = 23  # backward
battery_pin = 4
fecho_pin = 24
ftrig_pin = 25
becho_pin = 8
btrig_pin = 7
light_pin = 6

# motor variables
deltaX = 0.0
deltaY = 0.0
lastdeltaX = 0.0
lastdeltaY = 0.0
maxdeltaX = 100.0
maxdeltaY = 200.0
speedcontrol = 0
speedmodifer = 0.6

# SR04 variables
fdistance = 0.00
bdistance = 0.00
maxdistance = 3000
lastfdistance = 0.00
lastbdistance = 0.00
lastfultrasound = time.time()
lastbultrasound = time.time()
stopdistance = 15
ultrasoundinterval = 10

# battery variables & ADC ADS1115 setup
adc = Adafruit_ADS1x15.ADS1115()
GAIN = 1
# voltage divider used
R1 = 36000.0
R2 = 16000.0
# variance compared to voltage measured
variance = 0.08
# low voltage limit
vmin = 10.2
vmax = 12.46
vperc = 0.0
valarm = 10.5
# ADC read channel for lipo battery
ADCchannel = 0
# set initial values
ADCvalue = 0.0
voltage = 0.0
vin = 0.0
lastbatterycheck = time.time()
batterycheckinterval = 3.0 # 3 seconds

# set up logging
setuplogger()

# setup mqtt
client = mqtt.Client(client_id = mqttuser)
reloadMQTT()
logoutput("loaded variables")

# publish ip address
getPublicIP()
getPrivateIP()

# setup sensor
GPIO.setmode(GPIO.BCM)
GPIO.setup(battery_pin, GPIO.IN)
GPIO.setup(ftrig_pin, GPIO.OUT)
GPIO.setup(fecho_pin, GPIO.IN)
#GPIO.setup(btrig_pin, GPIO.OUT)
#GPIO.setup(becho_pin, GPIO.IN)
GPIO.setup(light_pin, GPIO.OUT, initial=0 )
logoutput("initialized sensors/outputs")

while True:  
  currenttime = time.time()
  time.sleep(0.2)

  # check battery sensor
  if (currenttime - lastbatterycheck >= batterycheckinterval):
    checkbattery(ADCchannel, GAIN)
    getPublicIP()
    getPrivateIP()

  #checkbultrasound(btrig_pin, becho_pin)

  checkfultrasound(ftrig_pin, fecho_pin, 0)
