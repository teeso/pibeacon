#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

# karl wachs 2018-04-21
#  copied pieces of code from various sources (adafruit, githubs ... )
#  most posted codes had issues and did not run completely #
#
#  this will read a PMS5003
#	connect +5V (not 3.3) ground and RX on the RPI	 to	  +5V GND TX on the sensor
#
#


import sys, os, time, json, subprocess,copy


sys.path.append(os.getcwd())
import	piBeaconUtils	as U
import	piBeaconGlobals as G
G.program = "pmairquality"
G.debug = 0


import serial 
import struct

import RPi.GPIO as GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)



class thisSensorClass:
	def __init__(self,	serialPort="/dev/ttyAMA0"):

		self.ser			= serial.Serial()
		self.ser.port		= serialPort 
		self.ser.stopbits	= serial.STOPBITS_ONE
		self.ser.bytesize	= serial.EIGHTBITS
		self.ser.baudrate	= 9600
		self.ser.timeout	= 1
		self.debugPrint		= 0
		

		self.ser.open()

	def getData(self): 
		nGoodMeasurements	= 0
		acumValues			= [ 0 for ii in range(12)]
		receivedCharacters	= ""
		self.debugPrint = G.debug
		try:
			for jj in range(3): # do 3 comple reads
			
				if jj > 0 : # sleep max 2 secs between each read, remember time out = 1 , = if failed read there is a 1 sec wait anyway
					if sleepTime > 0: time.sleep(sleepTime) 
					
				self.ser.flushInput()
				complePackage		 = ""
				receivedCharacters	 = ""
				sleepTime			 = 3
				completeRead = False
				
				for ii in range(3): # try each read max 3 times
					sleepTime -= 1
					receivedCharacters = self.ser.read(32)	# read up to 32 bytes

					# debug printout 
					if self.debugPrint > 1:	  print len(receivedCharacters), (":".join("{:02x}".format(ord(c)) for c in receivedCharacters))

					complePackage += receivedCharacters
				
					# find start of message
					while len(complePackage) > 1 and ord(complePackage[0]) != 66 and ord(complePackage[1]) != 77:	 # looking for	0x42 and 0x4d:
						complePackage = complePackage[1:] # drop first byte if wrong

					if len(complePackage) < 32:
						if self.debugPrint >0:	 print "complePackage not complete (32 bytes): " , len(complePackage), " continue to read"
						continue # to read
				
					frameLen = ord(complePackage[3])

					if frameLen != 28:
						if self.debugPrint >0:	 print "frameLength not correct (should be 28), is : ", frameLen, " try to read again"
						complePackage = ""
						continue

					# unpack and asign integers to list	 starting at pos 5 (=0...4)
					try:
						theValues = struct.unpack(">HHHHHHHHHHHHHH", complePackage[4:32])
					except Exception, e:
						print  e, "unpacking error,	 len of package: ", len(complePackage)
						complePackage = ""
						continue

				
					# calculate checksum
					check = 0
					for cc	in complePackage[0:30]:
						check += ord(cc)
					## print check, checksum
	
					# compare to send checksum
					if check != theValues[-1]:
						print "checksum not correct,  calculated:", check,", returned: ", theValues[-1]
						complePackage =""
						continue
						
					completeRead = True	 
					## add up values for average, use only first 12	 ignore skip, checksum	
					for kk in range(len(acumValues)):
						acumValues[kk] += theValues[kk]
					nGoodMeasurements += 1
					break
					
				if not completeRead:
					if self.debugPrint >0: print " not complete read, tried 3 times" 
			
			if nGoodMeasurements == 0: return "badSensor"
			
			# calculate average w proper rounding
			for kk in range(len(acumValues)):
				acumValues[kk] = int( float(acumValues[kk]) / nGoodMeasurements	 + 0.5 )
			

			if self.debugPrint	> 2: # debug print out 
				print "---------------------------------------"
				print "Concentration Units (standard)"
				print "PM 1.0: %d\tPM2.5: %d\tPM10: %d" % (acumValues[0], acumValues[1], acumValues[2])
				print "---------------------------------------"
				print "Concentration Units (environmental)"
				print "PM 1.0: %d\tPM2.5: %d\tPM10: %d" % (acumValues[3], acumValues[4], acumValues[5])
				print "---------------------------------------"
				print "Particle size		Count"
				print " > 0.3um / 0.1L air:", acumValues[6]
				print " > 0.5um / 0.1L air:", acumValues[7]
				print " > 1.0um / 0.1L air:", acumValues[8]
				print " > 2.5um / 0.1L air:", acumValues[9]
				print " > 5.0um / 0.1L air:", acumValues[10]
				print " > 10 um / 0.1L air:", acumValues[11]
				print "---------------------------------------"
			return acumValues
		except	Exception, e:
			U.toLog(-1, u"in Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e),doPrint=True)
		U.toLog(-1, " bad read, ..	receivedCharacters"+ str(len(receivedCharacters))+":"+str(":".join("{:02x}".format(ord(c)) for c in receivedCharacters)), doPrint=True)
		return "badSensor"



 # ===========================================================================
# read params
# ===========================================================================

#################################		 
def readParams():
	global sensorList, sensors, logDir, sensor,	 sensorRefreshSecs, displayEnable
	global rawOld
	global deltaX, minSendDelta
	global oldRaw, lastRead
	global startTime
	global resetPin
	try:



		inp,inpRaw,lastRead2 = U.doRead(lastTimeStamp=lastRead)
		if inp == "": return
		if lastRead2 == lastRead: return
		lastRead   = lastRead2
		if inpRaw == oldRaw: return
		oldRaw	   = inpRaw
		
		externalSensor=False
		sensorList=[]
		sensorsOld= copy.copy(sensors)


		
		U.getGlobalParams(inp)
		  
		if "sensorList"			in inp:	 sensorList=			 (inp["sensorList"])
		if "sensors"			in inp:	 sensors =				 (inp["sensors"])
		if "debugRPI"			in inp:	 G.debug=			  int(inp["debugRPI"]["debugRPISENSOR"])

 
		if sensor not in sensors:
			U.toLog(-1, G.program+" is not in parameters = not enabled, stopping BME680.py" )
			exit()
			

		U.toLog(1, G.program+" reading new parameter file" )


 

		if sensorRefreshSecs == 91:
			try:
				xx	   = str(inp["sensorRefreshSecs"]).split("#")
				sensorRefreshSecs = float(xx[0]) 
			except:
				sensorRefreshSecs = 91	  
		deltaX={}
		restart = False
		for devId in sensors[sensor]:
			deltaX[devId]  = 0.1
			if "resetPin"			in sensors[sensor][devId]:		resetPin[devId]= sensors[sensor][devId]["resetPin"]

			old = sensorRefreshSecs
			try:
				if "sensorRefreshSecs" in sensors[sensor][devId]:
					xx = sensors[sensor][devId]["sensorRefreshSecs"].split("#")
					sensorRefreshSecs = float(xx[0]) 
			except:
				sensorRefreshSecs = 12	  
			

			old = deltaX[devId]
			try:
				if "deltaX" in sensors[sensor][devId]: 
					deltaX[devId]= float(sensors[sensor][devId]["deltaX"])/100.
			except:
				deltaX[devId] = 0.15
			if old != deltaX[devId]: restart = True

			old = minSendDelta
			try:
				if "minSendDelta" in sensors[sensor][devId]: 
					minSendDelta= float(sensors[sensor][devId]["minSendDelta"])
			except:
				minSendDelta = 5.
			if old != minSendDelta: restart = True


				
			if devId not in thisSensor or  restart:
				startSensor(devId)
				if thisSensor[devId] =="":
					return
			U.toLog(-1," new parameters read: minSendDelta:"+unicode(minSendDelta)+"   deltaX:"+unicode(deltaX[devId])+";  sensorRefreshSecs:"+unicode(sensorRefreshSecs) )
				
		deldevID={}		   
		for devId in thisSensor:
			if devId not in sensors[sensor]:
				deldevID[devId]=1
		for dd in  deldevID:
			del thisSensor[dd]
		if len(thisSensor) ==0: 
			####exit()
			pass

	except	Exception, e:
		U.toLog(-1, u"in Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e),doPrint=True)
		U.toLog(-1,str(sensors[sensor]) )
		



def startSensor(devId):
	global sensors,sensor
	global startTime
	global thisSensor, firstValue
	U.toLog(-1,"==== Start "+G.program+" ===== ")
	startTime =time.time()
 
	try:
		sP = U.getSerialDEV() 
		thisSensor[devId]  = thisSensorClass(serialPort = sP)
		
	except	Exception, e:
		U.toLog(-1, u"in Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))
		thisSensor[devId] =""
	return


#################################
def getValues(devId):
	global sensor, sensors,	 thisSensor, badSensor
	global startTime
	global gasBaseLine, gasBurnIn, lastMeasurement, calibrateIfgt,setCalibration, firstValue
	try:
		if thisSensor[devId] =="": 
			badSensor +=1
			return "badSensor"

		retData= thisSensor[devId].getData()
		if retData != "badSensor": 
			data = {"pm10_standard":	retData[0], 
					"pm25_standard":	retData[1], 
					"pm100_standard":	retData[2], 
					"pm10_env":			retData[3], 
					"pm25_env":			retData[4], 
					"pm100_env":		retData[5], 
					"particles_03um":	retData[6], 
					"particles_05um":	retData[7], 
					"particles_10um":	retData[8], 
					"particles_25um":	retData[9], 
					"particles_50um":	retData[10], 
					"particles_100um":	retData[11]	 }
			U.toLog(2, unicode(data)) 
			badSensor = 0
			return data
	except	Exception, e:
		U.toLog(-1, u"in Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))
	badSensor+=1
	if badSensor >3: return "badSensor"
	return ""

def resetSensor(devId =""):
	global resetPin
	for id in resetPin:
		if devId == "" or id == devId:
			pin = resetPin[id]
			if pin == "": continue
			pin = int(pin)
			if pin > 26:  continue 
			if pin < 2:	  continue	
			U.toLog(-1, u"resetting pmAirquality device")
			GPIO.setup(pin, GPIO.OUT)
			GPIO.output(pin, True)
			time.sleep(0.1)
			GPIO.output(pin,False)
			time.sleep(0.5)
			GPIO.output(pin,True)
	return 



############################################
global rawOld
global sensor, sensors, badSensor
global deltaX, thisSensor, minSendDelta
global oldRaw, lastRead
global startTime, firstValue
global resetPin

resetPin					= {}
firstValue					= True
startTime					= time.time()
lastMeasurement				= time.time()
oldRaw						= ""
lastRead					= 0
minSendDelta				= 5.
G.debug						= 5
loopCount					= 0
sensorRefreshSecs			= 91
NSleep						= 100
sensorList					= []
sensors						= {}
sensor						= G.program
quick						= False
display						= "0"
output						= {}
badSensor					= 0
sensorActive				= False
loopSleep					= 0.5
rawOld						= ""
thisSensor					= {}
deltaX						= {}
displayEnable				= 0
myPID						= str(os.getpid())
U.killOldPgm(myPID,G.program+".py")# kill old instances of myself if they are still running


if U.getIPNumber() > 0:
	time.sleep(10)
	exit()

readParams()

time.sleep(1)

lastRead = time.time()

U.echoLastAlive(G.program)

resetSensor()

lastValues0			= {"particles_03um":0,"particles_05um":0,"particles_10um":0,"particles_25um":0,"particles_50um":0, "particles_100m":0}
lastValues			= {}
lastValues2			= {}
lastData			= {}
lastSend			= 0
lastDisplay			= 0
startTime			= time.time()
G.lastAliveSend		= time.time() -1000


sensorWasBad = False
while True:
	try:
		tt = time.time()
		sendData = False
		if sensor in sensors:
			data = {"sensors": {sensor:{}}}
			for devId in sensors[sensor]:
				if devId not in lastValues: 
					lastValues[devId]  =copy.copy(lastValues0)
					lastValues2[devId] =copy.copy(lastValues0)
				values = getValues(devId)
				if values == "": continue
				data["sensors"][sensor][devId]={}
				if values =="badSensor":
					sensorWasBad = True
					data["sensors"][sensor][devId]="badSensor"
					if badSensor < 5: 
						U.toLog(-1," bad sensor")
						U.sendURL(data)
						resetSensor(devId=devId)
					else:
						U.restartMyself(param="", reason="badsensor",doPrint=True)
					lastValues2[devId] =copy.copy(lastValues0)
					lastValues[devId]  =copy.copy(lastValues0)
					continue
				elif values["particles_03um"] !="" :
					
					data["sensors"][sensor][devId] = values
					deltaN =0
					for xx in lastValues0:
						try:
							current = float(values[xx])
							delta= current-lastValues2[devId][xx]
							deltaN= max(deltaN,abs(delta) / max (0.5,(current+lastValues2[devId][xx])/2.))
							lastValues[devId][xx] = current
						except: pass
				else:
					continue
				if sensorWasBad or (   ( deltaN > deltaX[devId]	 ) or  (  tt - abs(G.sendToIndigoSecs) > G.lastAliveSend  ) or	quick	) and  ( tt - G.lastAliveSend > minSendDelta ):
						sensorWasBad = False
						sendData = True
						if not firstValue: # do not send first measurement, it is always OFFFF
							lastValues2[devId] = copy.copy(lastValues[devId])
						firstValue = False
		if sendData and time.time() - startTime > 10: 
			U.sendURL(data)

		loopCount +=1

					 
		U.echoLastAlive(G.program)

		if loopCount %2 ==0:
			xx= time.time()
			if xx - lastRead > 5.:	
				readParams()
				lastRead = xx

		nsleep = int(max(5,sensorRefreshSecs-5)/5.)
		for ii in range(nsleep):
				quick = U.checkNowFile(G.program)				 
				if U.checkResetFile(G.program): 
					quick = True
					for devId in sensors[sensor]:
						resetSensor(devId=devId) 
				if quick: break
				time.sleep(5.)

	except	Exception, e:
		U.toLog(-1, u"in Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))
		time.sleep(5.)
sys.exit(0)
		
