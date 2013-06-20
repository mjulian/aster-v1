from flask import Flask
from flask import render_template
from flask import abort
import os
from collections import defaultdict
from ordereddict import OrderedDict

app = Flask(__name__)

graphiteServer = "graphite.mikejulian.com"

# Create an ordereddict so that the metric options appear in this order
# Key names show in the menu, while first and second values are Graphite metric names
# Third value is used to decide what view options to show
metrics = OrderedDict()
metrics['throughput'] = ['ifHCInbyte', 'ifHCOutbyte', 'octets']                  # octets
metrics['errors'] = ['ifInErrors', 'ifOutErrors', 'octets']        # octets
metrics['discards'] = ['ifInDiscards', 'ifOutDiscards', 'packets'] # Packets
metrics['unicast'] = ['ifInUcastPkts', 'ifOutUcastPkts', 'packets']        # Packets
metrics['broadcast'] = ['ifInBroadcastPkts', 'ifOutBroadcastPkts', 'packets']      # Packets
metrics['multicast'] = ['ifInMulticastPkts', 'ifOutMulticastPkts', 'packets']      # Packets


def getDevices():
    # This function iterates through the whisper storage to determine what hosts and interfaces to show
    # Caveat: this could result in showing devices and interfaces which are no longer active

    # Dictionary comes out looking like this:
    #    {'interfaces': 
    #        {'ge-1/0/4.3810': {
    #            'cleanedName': 'ge-1_0_4--3810', 
    #            'actualName': 'ge-1/0/4.3810'
    #            }, 
    #         'xe-2/1/3': {
    #             'cleanedName': 'xe-2_1_3', 
    #             'actualName': 'xe-2/1/3'
    #            } 
    #        },
    #        'hostname': 'localhost'
    #    }

    whisperStorage = '/opt/graphite/storage/whisper/diamond/mjulian/snmp/devices'
    devices = []
    deviceEntry = defaultdict(dict)
    interfacesDict = defaultdict(dict)

    for host in os.listdir(whisperStorage):
        deviceEntry['hostname'] = host
        for interface in os.listdir(os.path.join(whisperStorage, host, 'snmp')):
            # Create a dict with two versions of the interface name: one that is the on-disk
            # name and one that is the "prettied" name. Reasoning: whisper cannot store metric names
            # which contain hyphens, and a period denotes a new tree--both items found in
            # networking gear (Cisco, Juniper)
            prettyInterface = interface.replace('_','/').replace('--','.')
            interfacesDict['interfaces'][prettyInterface] = {}
            interfacesDict['interfaces'][prettyInterface]['cleanedName'] = interface
            interfacesDict['interfaces'][prettyInterface]['actualName'] = prettyInterface
        deviceEntry.update(interfacesDict.copy())
        devices.append(deviceEntry.copy())
        deviceEntry.clear()
        interfacesDict.clear()
    return devices


# This function takes the prettied interface name and finds the on-disk name, which
# gets passed to the Graphite API URL
def getInterfaceName(devices, hostname, interface):
    for device in devices:
        if device['hostname'] == hostname:
            for iface in device['interfaces']:
                if device['interfaces'][iface]['actualName'] == interface:
                    return device['interfaces'][iface]['cleanedName']

@app.route('/')
@app.route('/index')
def index():
    hosts = getDevices()
    return render_template('base.html', devices=hosts, metrics=metrics)

@app.route('/graph/<host>/<path:interface>/<metric>/<timeperiod>/<viewOption>/<function>')
def graph(host,interface,metric,timeperiod,viewOption,function):
    graphiteMetricBase = "diamond.mjulian.interface.devices"
    hosts = getDevices()

    # Ordereddict to show time periods in this order
    # Key is what's shown on the page, values get passed to Graphite API
    timeperiods = OrderedDict()
    timeperiods['15m'] = ['-15min', 'now']
    timeperiods['1h'] = ['-1h', 'now']
    timeperiods['24h'] = ['-24h', 'now']
    timeperiods['7d'] = ['-7d', 'now']
    timeperiods['30d'] = ['-30d', 'now']
    timeperiods['6mo'] = ['-6mon', 'now']
    timeperiods['1y'] = ['-1y', 'now']

    # Ordereddict to show view options in this order
    # Key is used in the URL, value gets shown on the page
    viewOptions = OrderedDict()
    viewOptions['bps'] = 'Bits/sec'
    viewOptions['Bps'] = 'Bytes/sec'
    viewOptions['pps'] = 'Packets/sec'

    cleanedInterfaceName = getInterfaceName(hosts, host, interface)

    # Template uses 'default' for timeperiod, so we we set it here
    if timeperiod == "default":
        timeperiod = "1h"

    # Same as above. I used Bps as default because the counter from SNMP is already in octets
    if viewOption == "default":
        if metrics.get(metric)[2] == "packets":
            viewOption = "pps"
        else:
            viewOption = "Bps"

    # We use this variable to determine what view options are shown. See metrics dict above
    metricUnit = metrics.get(metric)[2]

    # From here on, we start building the URL to pass to Graphite
    rxTargetOverlay = None
    txTargetOverlay = None

    rxTarget = "%s.%s.interface.%s.%s" % (graphiteMetricBase, host, cleanedInterfaceName, metrics.get(metric)[0])
    txTarget = "%s.%s.interface.%s.%s" % (graphiteMetricBase, host, cleanedInterfaceName, metrics.get(metric)[1])

    rxTarget = "scaleToSeconds(" + rxTarget + ",1)"
    txTarget = "scaleToSeconds(" + txTarget + ",1)"

    if viewOption == "bps":
        rxTarget = "scale(" + rxTarget + ",0.125)"
        txTarget = "scale(" + txTarget + ",0.125)"

    if function == "average":
        rxTarget = "movingAverage(" + rxTarget + ",30)"
        txTarget = "movingAverage(" + txTarget + ",30)"

    if function == "95th":
        rxTargetOverlay = "nPercentile(" + rxTarget + ",95)"
        txTargetOverlay = "nPercentile(" + txTarget + ",95)"
        rxTargetOverlay = "alias(" + rxTargetOverlay + ",\"rx - 95th\")"
        txTargetOverlay = "alias(" + txTargetOverlay + ",\"tx - 95th\")"

    rxTarget = "alias(" + rxTarget + ",\"rx\")"
    txTarget = "alias(" + txTarget + ",\"tx\")"

    if rxTargetOverlay and txTargetOverlay:
        graphLink = "http://" + graphiteServer + "/render?from=" + timeperiods.get(timeperiod)[0] + "&until=" + timeperiods.get(timeperiod)[1] + "&width=900&height=450" + "&target=" + rxTarget + "&target=" + txTarget + "&target=" + rxTargetOverlay + "&target=" + txTargetOverlay + "&hideGrid=true&fontSize=14&margin=25&vtitle=" + viewOptions.get(viewOption)
    else:
        graphLink = "http://" + graphiteServer + "/render?from=" + timeperiods.get(timeperiod)[0] + "&until=" + timeperiods.get(timeperiod)[1] + "&width=900&height=450" + "&target=" + rxTarget + "&target=" + txTarget + "&hideGrid=true&fontSize=14&margin=25&vtitle=" + viewOptions.get(viewOption)

    return render_template('graph.html',
        metricUnit=metricUnit,
        viewOptions=viewOptions,
        metrics=metrics,
        timeperiods=timeperiods,
        devices=hosts,
        host=host,
        interface=interface,
        metric=metric,
        timeperiod=timeperiod,
        viewOption=viewOption,
        function=function,
        graph_link=graphLink
     )


if __name__ == '__main__':
    app.debug = True
    app.run('0.0.0.0')
