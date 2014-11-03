#! /usr/bin/python

"""
started with dispatch_async.py
Original code derived from Paul Malmsten, 2010, pmalmsten@gmail.com

This code:
- continuously reads the serial port from xbee radio stream
- dispatches incoming tcp packets to appropriate methods for processing in a separate thread.
- sends data to node-red tcp socket.

Libraries used:
https://pypi.python.org/pypi/XBee/2.1.0
https://pypi.python.org/pypi/simplejson/2.6.1
https://pypi.python.org/pypi/pyserial/2.5

"""

from xbee import XBee
from xbee.helpers.dispatch import Dispatch
import time
import serial
from datetime import datetime
import binascii
import socket
import sys, os
import simplejson
import syslog
import ConfigParser
import threading



# check that the config file exists
configfile = "/etc/tinaja/tinaja.conf"

if not os.path.isfile("/etc/passwd"):
    print "cannot locate config file: " + configfile
    sys.exit(1)

# get the config file info
try:
    config = ConfigParser.ConfigParser()
    config.read(configfile)

    PORT = config.get('tinaja', 'serialport')
    BAUD_RATE = config.getint('tinaja', 'baudrate')
    TIMEOUT = config.getint('tinaja', 'timeout')
    LOCALLOGPATH = config.get('tinaja', 'locallogpath')

    COLLECT_INTERVAL = config.getfloat('tinaja', 'collection_interval')

    # node-red socket info
    SOCKET_SERVER = config.get('tinaja', 'nr_server')
    SOCKET_PORT_SNSR = config.getint('tinaja', 'snsr_socketport')
    SOCKET_PORT_CNTR = config.getint('tinaja', 'cntr_socketport')

    # local socket server info
    HOST_SERVER = config.get('tinaja', 'hostserver')
    HOST_PORT = config.getint('tinaja', 'hostport')
    HOST_BACKLOG = config.getint('tinaja', 'hostbacklog')
    HOST_SIZE = config.getint('tinaja', 'hostsize')
except Exception, e:
    print "TLSM: Configuration error: ", e.message
    syslog.syslog("TLSM: Configuration error: " + e.message)

# starting up...
print ""
print "------------------- starting: " + os.path.basename(sys.argv[0])
syslog.syslog("TLSM - Tinaja Labs Sensor Manager: "+os.path.basename(sys.argv[0])+" started")

keepGoing = True

# counters for reporting data through-put
inBoundCount = 0
outBoundCount = 0
countSeconds = 15

# Open serial port
# ser = serial.Serial(PORT, BAUD_RATE,timeout=TIMEOUT)
ser = serial.Serial(PORT, BAUD_RATE)
syslog.syslog("Serial port opened: "+ str(ser))


##############################################################
def clamp(n, minn, maxn):
    if n < minn:
        return minn
    elif n > maxn:
        return maxn
    else:
        return n

##############################################################
def inADCRange(n):
    minn=0
    maxn=1024
    if n < minn:
        return minn
    elif n > maxn:
        return maxn
    else:
        return n

##############################################################
def hex2dec(hexVal):
    return int(binascii.hexlify(hexVal),16)

##############################################################
def sensorVal(sample, sensor):
    return sample[sensor]

##############################################################
# send to carbon/whisper - no longer needed
# def send2Socket(metric_path, value):
#     global outBoundCount

#     if (value <=0):
#         return

#     cValue = clamp(value, 0, 1023)

#     timestamp = int(time.time())
#     message = '%s %s %d\n' % (metric_path, cValue, timestamp)
#     # print 'sending socket message:\n%s' % message
#     syslog.syslog("TLSM: "+ 'sending socket message:\n%s' % message)

#     sock = socket.socket()
#     sock.connect((SOCKET_SERVER, SOCKET_PORT))
#     sock.sendall(message)
#     sock.close()

##############################################################
def sendSensor2NodeRed(jsonMsg):
    global outBoundCount

    if not jsonMsg:
        return

    timestamp = int(time.time())

    sock = socket.socket()
    sock.connect((SOCKET_SERVER, SOCKET_PORT_SNSR))
    sock.sendall(jsonMsg)
    sock.close()
    outBoundCount += 1

##############################################################
def sendCounts2NodeRed():
    global outBoundCount
    global inBoundCount

    print "sendCounts2NodeRed - outBoundCount:",outBoundCount,"inBoundCount:",inBoundCount

    data = { "id": "datacounts", "data" : {"outbound": outBoundCount, "inbound": inBoundCount }}
    jsonMsg = simplejson.dumps(data)

    if not jsonMsg:
        return

    timestamp = int(time.time())

    sock = socket.socket()
    sock.connect((SOCKET_SERVER, SOCKET_PORT_CNTR))
    sock.sendall(jsonMsg)
    sock.close()
    outBoundCount =0
    inBoundCount =0


##############################################################
# send a message to node red every x minutes with some counters
def sendCounterThread():
  threading.Timer(10.0, sendCounterThread).start()
  sendCounts2NodeRed()

sendCounterThread()


##############################################################
def islogcurrent(lofilename):

    if lofilename == None:
        return false

    TimeStamp = "%s" % (time.strftime("%Y%m%d"))
    checkname = LOCALLOGPATH+TimeStamp+".csv"

    if lofilename == checkname:
        return True
    else:
        return False


##############################################################
def getlogfile():
# open our datalogging file
# CJ, 05.13.2011, included /logs/ directory under www

    TimeStamp = "%s" % (time.strftime("%Y%m%d"))
    # print "TimeStamp", TimeStamp 
    filename = LOCALLOGPATH+TimeStamp+".csv"   # where we will store our flatfile data

    lfile = None
    try:
        lfile = open(filename, 'r+')
    except IOError:
        # didn't exist yet
        lfile = open(filename, 'w+')
        lfile.write("#Date, time, sensornum, value\n");
        lfile.flush()

    return lfile


##############################################################
# log to the local CSV file
def logtocsv(lnSensorNum, lnAvgUnits, loLogfile):

        # Lets log it! Seek to the end of our log file
        if loLogfile:
            loLogfile.seek(0, 2) # 2 == SEEK_END. ie, go to the end of the file
            loLogfile.write(time.strftime("%Y %m %d, %H:%M")+", "+
                          str(lnSensorNum)+", "+
                          str(lnAvgUnits)+"\n")
            loLogfile.flush()
            # print "Sensor# ", lnSensorNum, "logged ", lnAvgUnits, " to ", loLogfile.name



##############################################################
# Create handlers for various packet types
def status_handler(name, packet):
    try:
        # print "Status Update - Status is now: ", packet['status']
        # print "Status handler: ", name, packet
        syslog.syslog("TLSM Status Handler: "+ name + ", " + packet)
    except Exception, e:
        print "Status exception:", e.message
        syslog.syslog("TLSM status handler exception: "+ e.message)


##############################################################
def io_sample_handler(name, packet):
    global inBoundCount
    try:
        if packet:
            # print "Samples handler: ", name, packet
            inBoundCount += 1

            srcAddr = hex2dec(packet['source_addr'])
            # print "Samples handler: ", srcAddr,"-", packet['samples'][0]['adc-0'], packet['samples'][0]['adc-1'], packet['samples'][0]['adc-2'], packet['samples'][0]['adc-3']
            syslog.syslog("Samples handler," + str(srcAddr)+","+str(packet['samples'][0]['adc-0']) +","+ str(packet['samples'][0]['adc-1']) +","+ str(packet['samples'][0]['adc-2']) +","+ str(packet['samples'][0]['adc-3']))

            sensorV0 = clamp(inADCRange(sensorVal(packet['samples'][0],'adc-0')), 0, 1023)
            sensorV1 = clamp(inADCRange(sensorVal(packet['samples'][0],'adc-1')), 0, 1023)
            sensorV2 = clamp(inADCRange(sensorVal(packet['samples'][0],'adc-2')), 0, 1023)
            sensorV3 = clamp(inADCRange(sensorVal(packet['samples'][0],'adc-3')), 0, 1023)

            # data = { "sensor_id": srcAddr, "V0": sensorV0, "V1": sensorV1, "V2": sensorV2, "V3": sensorV3 }
            data = { "sensor_id": srcAddr, "data" : {"V0": sensorV0, "V1": sensorV1, "V2": sensorV2, "V3": sensorV3 }}

            data_json = simplejson.dumps(data)
            sendSensor2NodeRed(data_json)
            # print data
            # print srcAddr, "\t", sensorV0, "\t", sensorV1, "\t", sensorV2, "\t", sensorV3
            # time.sleep(.4)
            time.sleep(COLLECT_INTERVAL)

    except KeyboardInterrupt:
        print "break in io_sample_handler!"
        syslog.syslog("TLSM break in io_sample_handler!")
        return
        # break
        # xbee.halt()
        # ser.close()
        # print "Halted & closed!"

    except Exception, e:
        print "Sample exception:", e.message
        syslog.syslog("TLSM sample handler exception: "+ e.message)
        return



###############################################################################################
# When a Dispatch is created with a serial port, it will automatically
# create an XBee object on your behalf for accessing the device.
# If you wish, you may explicitly provide your own XBee:
#
#  xbee = XBee(ser)
#  dispatch = Dispatch(xbee=xbee)
#
# Functionally, these are the same.
dispatch = Dispatch(ser)

# Register the packet handlers with the dispatch:
#  The string name allows one to distinguish between mutiple registrations
#   for a single callback function
#  The second argument is the function to call
#  The third argument is a function which determines whether to call its
#   associated callback when a packet arrives. It should return a boolean.
dispatch.register(
    "status", 
    status_handler, 
    lambda packet: packet['id']=='status'
)

dispatch.register(
    "io_data", 
    io_sample_handler,
    lambda packet: packet['id']=='rx_io_data'
)

# Create API object, which spawns a new thread
# Point the asyncronous callback at Dispatch.dispatch()
#  This method will dispatch a single XBee data packet when called
xbee = XBee(ser, callback=dispatch.dispatch)




###############################################################################################
# main thread

# host = '192.168.1.3' 
# host = 'localhost'
# host = '192.168.0.38'
# port = 4056 
# backlog = 10 
# size = 512 


# HOST_SERVER = config.get('tinaja', 'hostserver')
# HOST_PORT = config.getint('tinaja', 'hostport')
# HOST_BACKLOG = config.getint('tinaja', 'hostbacklog')
# HOST_SIZE = config.getint('tinaja', 'hostsize')

# set up the socket server
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
    s.bind((HOST_SERVER,HOST_PORT))
    s.listen(HOST_BACKLOG)
    print "Socket now listening on: ", HOST_SERVER,HOST_PORT
    syslog.syslog("TLSM: Socket is listening on: "+HOST_SERVER +":"+str(HOST_PORT))

except Exception, e:
    print e.message
    s.close()
    keepGoing = False
    sys.exit(1)

# Do other stuff in the main thread
while keepGoing == True:
    try:
        while True: 
            newsocket, address = s.accept()
            print "Connected from: ", address

            while True:
                data = newsocket.recv(HOST_SIZE)
                if not data:
                    print 'no input'
                    break

                print "received data from:", address, "\t", data

                radioMsg = data.split(":")
                # print hex(int(radioMsg[0])), radioMsg[1]

                radioAddr = chr(0) + chr(int(radioMsg[0]))
                # print "radioAddr", radioAddr

                radioCmd = '\x04'
                if radioMsg[1] == "HI":
                    radioCmd = '\x05'

                for x in xrange(4):
                    xbee.remote_at(dest_addr=radioAddr,frame_id=b"A",command='D4',parameter=radioCmd)
                    time.sleep(.13)


            print "diconnected from: ", address

    except KeyboardInterrupt:
        print "keyboard break!"
        keepGoing = False
        break

    except Exception, e:
        print "general error", e.message
        keepGoing = False
        s.close()
        print "exception: socket closed..."

    finally:
        keepGoing = False
        s.close()
        print "finally: socket closed..."

# halt() must be called before closing the serial
# port in order to ensure proper thread shutdown
xbee.halt()
ser.close()
s.close()
print "eof: Halted & closed!"




## this is the structure of the basic config file
## copy it to /etc/tinaja/tinaja.conf

# [tinaja]
# serialport = /dev/ttyAMA0
# baudrate = 9600
# timeout=0

# locallogpath = /home/data/

# nr_server = redbone
# nr_socketport = 2007

# hostserver = 192.168.0.38
# hostport = 4056 
# hostbacklog = 10 
# hostsize = 512 
