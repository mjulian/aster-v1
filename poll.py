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

objects32 = [('1.3.6.1.2.1.2.2.1.10', 'rx'),               # Unit: Octets
             ('1.3.6.1.2.1.2.2.1.11', 'rx-ucast'),         # Unit: Packets
             ('1.3.6.1.2.1.2.2.1.13', 'rx-discards'),      # Unit: ???
             ('1.3.6.1.2.1.2.2.1.14', 'rx-errors'),        # Unit: Octets
             ('1.3.6.1.2.1.2.2.1.15', 'rx-unknownProtos'), # Unit: ???
             ('1.3.6.1.2.1.2.2.1.16', 'tx'),               # Unit: Octets
             ('1.3.6.1.2.1.2.2.1.17', 'tx-ucast'),         # Unit: Packets
             ('1.3.6.1.2.1.2.2.1.19', 'tx-discards'),      # Unit: ???
             ('1.3.6.1.2.1.2.2.1.20', 'tx-errors'),        # Unit: Octets
             ('1.3.6.1.2.1.2.2.1.2', 'descr')]             # Interface name (not alias)

objects64 = [('1.3.6.1.2.1.31.1.1.1.5', 'rx64'),           # Unit: Octets
             ('1.3.6.1.2.1.31.1.1.1.6', 'rx-ucast64'),     # Unit: Packets
             ('1.3.6.1.2.1.31.1.1.1.7', 'rx-mcast64'),     # Unit: Packets
             ('1.3.6.1.2.1.31.1.1.1.8', 'rx-bcast64'),     # Unit: Packets
             ('1.3.6.1.2.1.2.2.1.14', 'rx-errors'),        # Unit: Octets
             ('1.3.6.1.2.1.31.1.1.1.9', 'tx64'),           # Unit: Octets
             ('1.3.6.1.2.1.31.1.1.1.10', 'tx-ucast64'),    # Unit: Packets
             ('1.3.6.1.2.1.31.1.1.1.11', 'tx-mcast64'),    # Unit: Packets
             ('1.3.6.1.2.1.31.1.1.1.12', 'tx-bcast64'),    # Unit: Packets
             ('1.3.6.1.2.1.2.2.1.20', 'tx-errors'),        # Unit: Octets
             ('1.3.6.1.2.1.2.2.1.2', 'descr')]             # Interface name (not alias)

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
    package = pickle.dumps(tuples, 1)
    size = struct.pack('!L', len(package))
    sock.sendall(size)
    sock.sendall(package)
    endTime = time.time() - startTime
    print "Graphite Run time:", str(datetime.timedelta(seconds=endTime))

if sys.argv[3] == "poll":
    while True:
        try:
            print "Starting poll"
            poll(ip, comm, objects64)
            prepGraphite()
            print "Sleeping for ten seconds"
            time.sleep(10)
        except KeyboardInterrupt:
           print "\n\n poll.py: Killed by user input.\n\n"
           sys.exit()

if sys.argv[3] == "getports":
    availablePorts = cleanPortNames(snmpWalk(comm, ip, objects32[9][0]))
    for ports in availablePorts:
        print ports
