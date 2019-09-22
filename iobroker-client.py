import paho.mqtt.client as mqtt
import os.path
import time

from qmc5883 import QMCClient

# e.g. IObroker mqtt adapter:
MQTT_HOST = "192.168.0.100"
MQTT_TOPIC = "gas/value"

# current gas counter
INITIAL_VALUE = 2650.36

# current counter will be persisted in
DATA_FILE = "/var/lib/qmc5883-gas/value"

# threshold of triggering the counter
TRIGGER_THRESHOLD = 14000

def readValue():
    f = open(DATA_FILE, "r")
    value = float(f.readline())
    f.close()
    return value


def writeValue(value):
    f = open(DATA_FILE, "w")
    f.write(str(value))
    f.close()


def publish(value):
    print MQTT_TOPIC + " " + str(INITIAL_VALUE)
    client.publish(MQTT_TOPIC, INITIAL_VALUE)


if not os.path.exists(DATA_FILE):
    print "Write initial value to data file: " + str(INITIAL_VALUE)
    if not os.path.exists(os.path.dirname(DATA_FILE)):
        os.makedirs(os.path.dirname(DATA_FILE))
    f = open(DATA_FILE, "w+")
    f.write(str(INITIAL_VALUE))
    f.close()
else:
    INITIAL_VALUE = readValue()

client = mqtt.Client()
print "Connecting to mqtt broker"
client.connect(MQTT_HOST)
publish(INITIAL_VALUE)
print "Connecting to gas meter"
q = QMCClient(5, TRIGGER_THRESHOLD)
q.init()

while 1 == 1:
    data = q.read()
    print data
    client.publish("gas/x", data['x'])
    client.publish("gas/y", data['y'])
    client.publish("gas/z", data['z'])
    client.publish("gas/B", data['b'])
    if(data['triggered'] == 1):
        INITIAL_VALUE += 0.01
        writeValue(INITIAL_VALUE)
        publish(INITIAL_VALUE)
    time.sleep(1)
