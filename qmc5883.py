import math
import time

import smbus


class QMCClient:
    # Register numbers
    X_LSB = 0x00
    CONFIG = 0x09
    STATUS = 0x06
    RESET = 0x0B

    # Bit values for the STATUS register
    STATUS_DRDY = 1
    STATUS_OVL = 2
    STATUS_DOR = 4

    # Oversampling values for the CONFIG register
    CONFIG_OS512 = 0b00000000

    # Range values for the CONFIG register
    CONFIG_2GAUSS = 0b00000000
    CONFIG_8GAUSS = 0b00010000
    # Rate values for the CONFIG register
    CONFIG_10HZ = 0b00000000
    CONFIG_50HZ = 0b00000100

    # Mode values for the CONFIG register
    CONFIG_CONTINUOUS = 0b00000001

    address = 0x0D
    trigger_hyst = 2000
    trigger_state = 0
    old_state = 0

    def __init__(self, i2c_channel, trigger_level):
        self.channel = i2c_channel
        self.trigger_level = trigger_level
        print "Init QMC5883 @ i2c-" + str(self.channel)
        self.bus = smbus.SMBus(self.channel)

    def write(self, reg, val):
        self.bus.write_byte_data(self.address, reg, val)

    def __read__(self, reg):
        return self.bus.read_byte_data(self.address, reg)

    # Convert val to signed value
    def twos_complement(self, val, len):
        if (val & (1 << len - 1)):
            val = val - (1 << len)
        return val

    # Convert two bytes from data starting at offset to signed word
    def convert_sw(self, data, offset):
        return self.twos_complement(data[offset] | data[offset + 1] << 8, 16)

    def init(self):

        # reset device
        self.write(self.RESET, 0x01)
        time.sleep(1)
        # init continous mode
        self.write(self.CONFIG, self.CONFIG_CONTINUOUS
                   | self.CONFIG_50HZ
                   | self.CONFIG_8GAUSS
                   | self.CONFIG_OS512)

    def ready(self):
        status = self.__read__(self.STATUS)
        print "ready: " + str(status)
        return status & self.STATUS_DRDY

    def __read(self):
        # self.ready()
        while not self.ready():
            time.sleep(0.1)
            print "waiting for DRDY"

        # read data from QMC5883
        raw = []
        for i in range(0, 6):
            raw.append(self.__read__(i))

        # get x,y,z values of magnetic induction
        data = dict()
        data['x'] = self.convert_sw(raw, 0)  # x
        data['y'] = self.convert_sw(raw, 2)  # y
        data['z'] = self.convert_sw(raw, 4)  # z
        data['b'] = math.sqrt(
            float(data['x'] * data['x']) +
            float(data['y'] * data['y']) +
            float(data['z'] * data['z']))

        return data

    def read(self):

        self.old_state = self.trigger_state
        data = self.__read()
        data['triggered'] = 0

        if data['b'] > self.trigger_level + self.trigger_hyst:
            self.trigger_state = 1
        elif data['b'] < self.trigger_level - self.trigger_hyst:
            self.trigger_state = 0

        if self.old_state == 0 and self.trigger_state == 1:
            data['triggered'] = 1

        return data
