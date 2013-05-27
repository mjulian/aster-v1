from subprocess import Popen, PIPE
import sys
from collections import defaultdict
import time
import socket
import datetime
import pickle
import struct
import ConfigParser

config = ConfigParser.ConfigParser()
config.read('config.ini')

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

def snmpwalk(community, ip, object):
    output = []
    command = "/usr/bin/snmpbulkwalk -m '' -M '' -c " + community + " -v 2c -Oenq " + ip + " " + object
    snmp_process = Popen(command, shell=True, stderr=PIPE, stdout=PIPE, universal_newlines=True)
    stdout, stderr = snmp_process.communicate()
    stdout = stdout.splitlines()
    for x in stdout:
        y = x.split()
        output.append(y)
    return output

def cleanData(data, context):
    snmpResults = defaultdict(dict)
    for oid, value in data:
        indexNumber = oid.rsplit('.')[-1]
        if context == "descr":
            value = value.strip('\"').replace('/','_').replace('.','_')
            snmpResults[indexNumber][context] = value
        else:
            snmpResults[indexNumber][context] = value
    return snmpResults

def correlate(snmpResults, context):
    for key, values in snmpResults.items():
        ports[key][context] = values[context]
    return

def poll(ip, community, objects):
    for oid, context in objects:
        output = snmpwalk(community, hostname, oid)
        correlate(cleanData(output, context), context)
    for key, values in ports.items():
        ports[values['descr']] = ports.pop(key)

def prepGraphite(host):
    carbonServer = 'localhost'
    carbonPort = 2004
    sock = socket.socket()
    sock.connect((carbonServer, carbonPort))
    startTime = time.time()
    tuples = ([])
    for key, values in ports.items():
        host = host.split('.',1)[0]
        for metricName, metricValue in values.items():
            if "descr" not in metricName:
                tuples.append(('net.%s.%s.%s' % (host, key, metricName), (int(time.time()), metricValue)))
    package = pickle.dumps(tuples, 1)
    size = struct.pack('!L', len(package))
    sock.sendall(size)
    sock.sendall(package)

if sys.argv[1] == "poll":
    while True:
        try:
            for hostname in config.sections():
                for communityString in config.items(hostname):
                    poll(hostname, communityString[1], objects64)
                    prepGraphite(hostname)
            time.sleep(10)
        except KeyboardInterrupt:
           print "\n\n poll.py: Killed by user input.\n\n"
           sys.exit()

