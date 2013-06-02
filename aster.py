from flask import Flask
from flask import render_template
from flask import abort
import os
from collections import defaultdict
from ordereddict import OrderedDict

app = Flask(__name__)

graphiteServer = "graphite.mikejulian.com"

metrics = OrderedDict()
metrics['throughput'] = ['rx', 'tx', 'octets']                  # octets
metrics['errors'] = ['rx-errors', 'tx-errors', 'octets']        # octets
metrics['discards'] = ['rx-discards', 'tx-discards', 'packets'] # Packets
metrics['unicast'] = ['rx-ucast', 'tx-ucast', 'packets']        # Packets
metrics['broadcast'] = ['rx-bcast', 'tx-bcast', 'packets']      # Packets
metrics['multicast'] = ['rx-mcast', 'tx-mcast', 'packets']      # Packets


def getDevices():
    whisperStorage = '/opt/graphite/storage/whisper'
    devices = []
    deviceEntry = defaultdict(dict)
    interfacesDict = defaultdict(dict)

    for folder in os.listdir(whisperStorage):
        if folder == "net":
            for host in os.listdir(os.path.join(whisperStorage, folder)):
                deviceEntry['hostname'] = host
                for interface in os.listdir(os.path.join(whisperStorage, folder, host)):
                    prettyInterface = interface.replace('_','/').replace('--','.')
                    interfacesDict['interfaces'][prettyInterface] = {}
                    interfacesDict['interfaces'][prettyInterface]['cleanedName'] = interface
                    interfacesDict['interfaces'][prettyInterface]['actualName'] = prettyInterface
                deviceEntry.update(interfacesDict.copy())
                devices.append(deviceEntry.copy())
                deviceEntry.clear()
                interfacesDict.clear()
    return devices

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
    hosts = getDevices()
    timeperiods = OrderedDict()
    timeperiods['15m'] = ['-15min', 'now']
    timeperiods['1h'] = ['-1h', 'now']
    timeperiods['24h'] = ['-24h', 'now']
    timeperiods['7d'] = ['-7d', 'now']
    timeperiods['30d'] = ['-30d', 'now']
    timeperiods['6mo'] = ['-6mon', 'now']
    timeperiods['1y'] = ['-1y', 'now']

    viewOptions = OrderedDict()
    viewOptions['bps'] = 'Bits/sec'
    viewOptions['Bps'] = 'Bytes/sec'
    viewOptions['pps'] = 'Packets/sec'

    cleanedInterfaceName = getInterfaceName(hosts, host, interface)

    if timeperiod == "default":
        timeperiod = "1h"

    if viewOption == "default":
        if metrics.get(metric)[2] == "packets":
            viewOption = "pps"
        else:
            viewOption = "Bps"

    metricUnit = metrics.get(metric)[2]

    rxTargetOverlay = None
    txTargetOverlay = None

    rxTarget = "net.%s.%s.%s" % (host, cleanedInterfaceName, metrics.get(metric)[0])
    txTarget = "net.%s.%s.%s" % (host, cleanedInterfaceName, metrics.get(metric)[1])

    rxTarget = "perSecond(" + rxTarget + ")"
    txTarget = "perSecond(" + txTarget + ")"

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
        graphLink = "http://" + graphiteServer + "/render?from=" + timeperiods.get(timeperiod)[0] + "&until=" + timeperiods.get(timeperiod)[1] + "&width=900&height=450" + "&target=" + rxTarget + "&target=" + txTarget + "&target=" + rxTargetOverlay + "&target=" + txTargetOverlay + "&hideGrid=true&fontSize=14&vtitle=" + viewOptions.get(viewOption)
    else:
        graphLink = "http://" + graphiteServer + "/render?from=" + timeperiods.get(timeperiod)[0] + "&until=" + timeperiods.get(timeperiod)[1] + "&width=900&height=450" + "&target=" + rxTarget + "&target=" + txTarget + "&hideGrid=true&fontSize=14&vtitle=" + viewOptions.get(viewOption)

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
