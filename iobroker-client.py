#!/usr/bin/env python3
import argparse
import os.path
import time
from datetime import datetime

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                 description="publish data read from either a QMC5883 or HMC5883 sensor and publish them to an MQTT broker")
parser.add_argument(      '--host',  type=str, required=True, default=argparse.SUPPRESS,
                    help='mqtt host name or ip')
parser.add_argument('-c', '--client', type=str, default="gasometer",
                    help='mqtt client id string')
parser.add_argument(      '--topic', type=str, default="gas/value",
                    help='mqtt topic')
parser.add_argument('-u', '--user',  type=str, default="mosquitto",
                    help='mqtt user name')
parser.add_argument(      '--pass',  type=str, required=True, default=argparse.SUPPRESS,
                    help='mqtt passwort. The password is read from stdin if its value is "-".')
parser.add_argument('-f', '--data-file', type=str, required=True, default=argparse.SUPPRESS,
                    help='file to continuously write value to, to provide persistance across restarts')
parser.add_argument('-i', '--initial-value', type=float, default=0.0,
                    help='initial value to use if the file given to --data-file does not exist yet')
parser.add_argument(      '--inc-value', type=float, default=0.01,
                    help='increment by this value for each trigger event')
parser.add_argument('-t', '--threshold', type=float, default=600.0,
                    help='threshhold value of when to trigger counter')
parser.add_argument('-s', '--sensor', choices=['qmc5883', 'hmc5883'], default='qmc5883',
                    help='type of sensor')
parser.add_argument(      '--debug-all-values', action='store_true',
                    help='publish not only triggered events, but all x, y, z and B values: very noisy')

args = vars(parser.parse_args())

MQTT_HOST  = args['host']
MQTT_TOPIC = args['topic']
MQTT_USER  = args['user']
if args['pass'] == '-':
    MQTT_PASSWD = sys.stdin.readline().rstrip('\n')
else:
    MQTT_PASSWD = args['pass']
if args['sensor'] == 'qmc5883':
    from qmc5883 import QMCClient as Client
else:
    from qmc5883 import HMCClient as Client
INITIAL_VALUE     = args['initial_value']
DATA_FILE         = args['data_file']
TRIGGER_THRESHOLD = args['threshold']

import paho.mqtt.client as mqtt

def readValue():
    f = open(DATA_FILE, "r")
    value = float(f.readline())
    f.close()
    return value


def writeValue(value):
    f = open(DATA_FILE, "w")
    f.write(str(value))
    f.close()
    return


client = mqtt.Client(client_id=args['client'], clean_session=False)
client.username_pw_set(MQTT_USER, MQTT_PASSWD)
client.connected_flag = False

def on_connect(client, userdata, flags, rc):
    print("ON CONNECT")
    if rc == 0:
        print("connected to broker")
        client.connected_flag = True
    else:
        print("connected failed")
def on_disconnect(client, userdata, rc):
    print("disconnected from broker")
    client.connected_flag = False

client.on_connect = on_connect
client.on_disconnect = on_disconnect

print("CONNECT")
client.loop_start()
client.connect(MQTT_HOST)
time.sleep(2)

def publish(value):
    if not client.connected_flag:
        print("Could not publish value because connection was down, restarting connection instead.")
        client.loop_start()
        try:
          client.connect(MQTT_HOST)
        except Exception as e:
          print("Unable to connect right now. Retrying later.")
          print(f"  Reason: {e}")
          pass
    # do not wait for connection if it still has to be established: we might loose
    # the counter steps that way, rather decide to not send this one increase but
    # the correct number next time instead
    else:
        print(MQTT_TOPIC + f' {{"time":"{datetime.now().timestamp()}","value": {round(value, 2)}}}')
        client.publish(MQTT_TOPIC, f'{{"time":"{datetime.now().timestamp()}","value": {round(value, 2)}}}', qos=0)
    #client.disconnect()

if not os.path.exists(DATA_FILE):
    print("Write initial value to data file: " + str(INITIAL_VALUE))
    if not os.path.exists(os.path.dirname(DATA_FILE)):
        os.makedirs(os.path.dirname(DATA_FILE))
    f = open(DATA_FILE, "w+")
    f.write(str(INITIAL_VALUE))
    value = INITIAL_VALUE
    f.close()
else:
    value = readValue()

publish(value)
print("Connecting to gas meter")
q = Client(1, TRIGGER_THRESHOLD)
q.init()

while True:
    data = q.read()
    print(data)
    if args['debug_all_values']:
        client.publish("gas/x", data['x'])
        client.publish("gas/y", data['y'])
        client.publish("gas/z", data['z'])
        client.publish("gas/B", data['b'])
    if data['triggered'] == 1:
        value += args['inc_value']
        writeValue(value)
        publish(value)
    else:
        time.sleep(0.5)
