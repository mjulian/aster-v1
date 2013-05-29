from flask import Flask
from flask import render_template
from flask import abort
import os
from collections import defaultdict

app = Flask(__name__)

graphiteServer = "graphite.mikejulian.com"

def getDevices():
    whisperStorage = '/opt/graphite/storage/whisper'
    devices = []
    deviceEntry = defaultdict(list)

    for folder in os.listdir(whisperStorage):
        if folder == "net":
            for host in os.listdir(os.path.join(whisperStorage, folder)):
                deviceEntry['hostname'] = host
                for interface in os.listdir(os.path.join(whisperStorage, folder, host)):
                    deviceEntry['interfaces'].append(interface)
                devices.append(deviceEntry.copy())
                deviceEntry.clear()
    return devices

@app.route('/')
@app.route('/index')
def index():
    hosts = getDevices()
    return render_template('base.html', devices=hosts)

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
    metrics = {    # Key (canonical name): Graphite name (rx), Graphite name (tx)
        'throughput': ['rx', 'tx'],
        'errors': ['rx-errors', 'tx-errors'],
        'discards': ['rx-discards', 'tx-discards'],
        'unicast': ['rx-ucast', 'tx-ucast']}
#        'broadcast': ['rx-bcast', 'tx-bcast64'],
#        'multicast': ['rx-mcast64', 'tx-mcast64']}

    if timeperiod == "default":
        timeperiod = "1h"
    if viewOption == "default":
        viewOption = "Bps"

    rxTarget = "derivative(net.%s.%s.%s)" % (host, interface, metrics.get(metric)[0])
    txTarget = "derivative(net.%s.%s.%s)" % (host, interface, metrics.get(metric)[1])

    if viewOption == "bps":
        rxTarget = "scale(scaleToSeconds(" + rxTarget + ",1),0.125)"
        txTarget = "scale(scaleToSeconds(" + txTarget + ",1),0.125)"

    if viewOption == "Bps":
        rxTarget = "scaleToSeconds(" + rxTarget + ",1)"
        txTarget = "scaleToSeconds(" + txTarget + ",1)"

    if function == "average":
        rxTarget = "average(" + rxTarget + ",30)"
        txTarget = "average(" + txTarget + ",30)"

    rxTarget = "alias(" + rxTarget + ",\"rx\")"
    txTarget = "alias(" + txTarget + ",\"tx\")"

    graphLink = "http://" + graphiteServer + "/render?from=" + timeperiods.get(timeperiod)[0] + "&until=" + timeperiods.get(timeperiod)[1] + "&width=900&height=450" + "&target=" + rxTarget + "&target=" + txTarget + "&hideGrid=true&fontSize=14"


    return render_template('graph.html', devices=hosts, host=host, interface=interface, metric=metric, timeperiod=timeperiod, viewOption=viewOption, function=function, graph_link=graphLink)

@app.errorhandler(500)
def internal_error(error):
    return "<h1>500 error</h1>"

if __name__ == '__main__':
    app.run('0.0.0.0')
