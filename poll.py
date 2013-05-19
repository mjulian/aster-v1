from subprocess import Popen, PIPE
import sys
from collections import defaultdict
import time
import socket
import datetime
import pickle
import struct

ip = sys.argv[1]
comm = sys.argv[2]

objects = [('1.3.6.1.2.1.2.2.1.16', 'tx'),
           ('1.3.6.1.2.1.2.2.1.10', 'rx'),
          ('1.3.6.1.2.1.2.2.1.11', 'ucast'),
          ('1.3.6.1.2.1.2.2.1.12', 'nucast'),
           ('1.3.6.1.2.1.2.2.1.13', 'discards'),
           ('1.3.6.1.2.1.2.2.1.14', 'errors'),
           ('1.3.6.1.2.1.2.2.1.2', 'descr')]

ports = defaultdict(dict)

def snmpWalk(community, ip, object):
    output = []
    command = "/usr/bin/snmpwalk -c " + comm + " -v 2c -On " + ip + " " + object + " 2> /dev/null"
    process = Popen(command, shell=True, stdout=PIPE)
    returnedData = process.communicate()
    for x in returnedData:
        if not x is None:
            output.append(x)
    return output

def cleanData(data, context):
    snmpResults = defaultdict(dict)
    data = data.splitlines()
    for lines in data:
        lines = lines.split()
        indexNumber = lines[0].rsplit('.')[-1]
        if context == "descr":
            lines[3] = lines[3].replace('/','_').replace('.','_')
            snmpResults[indexNumber][context] = lines[3]
        else:
            snmpResults[indexNumber][context] = lines[3]
    return snmpResults

def cleanPortNames(data):
    snmpResults = []
    for x in data:
        x = x.splitlines()
    for lines in x:
        lines = lines.split()
        snmpResults.append(lines[3])
    return snmpResults

def correlate(snmpResults, context):
    for key, values in snmpResults.items():
        ports[key][context] = values[context]
    return

def sendToGraphite(message):
    carbonServer = 'localhost'
    carbonPort = 2003
    sock = socket.socket()
    sock.connect((carbonServer, carbonPort))
    sock.sendall(message)
    #print "Sending message: %s" % message
    sock.close()

def poll(ip, community, objects):
    startTime = time.time()
    for oid, context in objects:
        output = snmpWalk(comm, ip, oid)
        if output:
            for data in output:
                correlate(cleanData(data, context), context)

    for key, values in ports.items():
        ports[values['descr']] = ports.pop(key)
    endTime = time.time() - startTime
    print "Polling Run time:", str(datetime.timedelta(seconds=endTime))

def prepGraphite():
    carbonServer = 'localhost'
    carbonPort = 2004
    sock = socket.socket()
    sock.connect((carbonServer, carbonPort))
    startTime = time.time()
    tuples = ([])
    for key, values in ports.items():
        hostname = ip.split('.',1)[0]
        for metricName, metricValue in values.items():
            if "descr" not in metricName:
                tuples.append(('net.%s.%s.%s' % (hostname, key, metricName), (int(time.time()), metricValue)))
   # print tuples
    package = pickle.dumps(tuples, 1)
    size = struct.pack('!L', len(package))
    sock.sendall(size)
    sock.sendall(package)
#    sendToGraphite(message)
    endTime = time.time() - startTime
    print "Graphite Run time:", str(datetime.timedelta(seconds=endTime))

if sys.argv[3] == "poll":
    while True:
        print "Starting poll"
        poll(ip, comm, objects)
        prepGraphite()
        print "Sleeping for ten seconds"
        time.sleep(10)

if sys.argv[3] == "getports":
    availablePorts = cleanPortNames(snmpWalk(comm, ip, objects[6][0]))
    for ports in availablePorts:
        print ports
