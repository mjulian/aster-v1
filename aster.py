from flask import Flask
from flask import render_template
from flask import abort
import os
from collections import defaultdict

app = Flask(__name__)

graphiteServer = "graphite.mikejulian.com"
metrics = {    # Key (canonical name): Graphite name (rx), Graphite name (tx)
    'throughput': ['rx', 'tx'],
    'errors': ['rx-errors', 'tx-errors'],
    'discards': ['rx-discards', 'tx-discards'],
    'unicast': ['rx-ucast', 'tx-ucast'],
    'broadcast': ['rx-bcast', 'tx-bcast64'],
    'multicast': ['rx-mcast64', 'tx-mcast64']}


def getDevices():
    whisperStorage = '/opt/graphite/storage/whisper'
    devices = []
    deviceEntry = defaultdict(list)

    for folder in os.listdir(whisperStorage):
        if folder == "net":
            for host in os.listdir(os.path.join(whisperStorage, folder)):
                deviceEntry['hostname'] = host
                for interface in os.listdir(os.path.join(whisperStorage, folder, host)):
                    interface = interface.replace('_','/').replace('-','.')
                    deviceEntry['interfaces'].append(interface)
                devices.append(deviceEntry.copy())
                deviceEntry.clear()
    return devices

@app.route('/')
@app.route('/index')
def index():
    hosts = getDevices()
    return render_template('base.html', devices=hosts, metrics=metrics)

@app.route('/graph/<host>/<interface>/<metric>/<timeperiod>/<viewOption>/<function>')
def graph(host,interface,metric,timeperiod,viewOption,function):
    hosts = getDevices()
    timeperiods = {    # Key (canonical name): From - Until
        '15m': ['-15min', 'now'],
        '1h': ['-1h', 'now'],
        '24h': ['-24h', 'now'],
        '7d': ['-7d', 'now'],
        '30d': ['-30d', 'now'],
        '6mo': ['-6mon', 'now'],
        '1y': ['-1y', 'now']}

    if timeperiod == "default":
        timeperiod = "1h"
    if viewOption == "default":
        viewOption = "Bps"

    rxTarget = "net.%s.%s.%s" % (host, interface, metrics.get(metric)[0])
    txTarget = "net.%s.%s.%s" % (host, interface, metrics.get(metric)[1])

    rxTarget = "keepLastValue(" + rxTarget + ")"
    txTarget = "keepLastValue(" + txTarget + ")"

    rxTarget = "perSecond(" + rxTarget + ")"
    txTarget = "perSecond(" + txTarget + ")"

    if viewOption == "bps":
        rxTarget = "scale(" + rxTarget + ",0.125)"
        txTarget = "scale(" + txTarget + ",0.125)"

#    elif viewOption == "Bps":
#        rxTarget = "perSecond(" + rxTarget + ")"
#        txTarget = "perSecond(" + txTarget + ")"

    if function == "average":
        rxTarget = "movingAverage(" + rxTarget + ",30)"
        txTarget = "movingAverage(" + txTarget + ",30)"


    rxTarget = "alias(" + rxTarget + ",\"rx\")"
    txTarget = "alias(" + txTarget + ",\"tx\")"

    graphLink = "http://" + graphiteServer + "/render?from=" + timeperiods.get(timeperiod)[0] + "&until=" + timeperiods.get(timeperiod)[1] + "&width=900&height=450" + "&target=" + rxTarget + "&target=" + txTarget + "&hideGrid=true&fontSize=14&vtitle=" + viewOption

    return render_template('graph.html', metrics=metrics, devices=hosts, host=host, interface=interface, metric=metric, timeperiod=timeperiod, viewOption=viewOption, function=function, graph_link=graphLink)


if __name__ == '__main__':
    app.debug = True
    app.run('0.0.0.0')
