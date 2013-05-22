from flask import Flask
from flask import render_template
import os
from collections import defaultdict
import json

app = Flask(__name__)

@app.route('/')
def index():
#    devices = [ {
#            'hostname': 'router1',
#            'interfaces': ['xe1/0/1', 'gi4/2/1']
#            }, 
#            {
#                'hostname': 'router2',
#                'interfaces': ['fa3/0/1', 'gi0/1/3']
#            }
#            ]

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
    return render_template('devices.html', devices=devices)


if __name__ == '__main__':
    app.run('0.0.0.0')
