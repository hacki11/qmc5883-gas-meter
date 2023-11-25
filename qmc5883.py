import math
import time

import smbus

# general class for functionality common to QMC and HMC
class XMCClient:
    # values that should be overwritten by child classes
    name          = "XMC5883"
    address       = 0x1e
    trigger_hyst  = 100
    big_endian    = False
    OFFSET_X      = 0
    OFFSET_Y      = 2
    OFFSET_Z      = 4

    # Bit values for the STATUS register
    STATUS_DRDY = 1

    # class-internal state variables
    trigger_state = 0
    old_state     = 0
    just_started  = True

    def __init__(self, i2c_channel, trigger_level):
        self.channel = i2c_channel
        self.trigger_level = trigger_level
        print(f"Init {self.name} @ i2c-{self.channel}")
        self.bus = smbus.SMBus(self.channel)

    def write(self, reg, val):
        self.bus.write_byte_data(self.address, reg, val)

    # read a single register
    def __read__(self, reg):
        return self.bus.read_byte_data(self.address, reg)

    # read a block: for use with the data registers which all should be read
    def __read_block__(self):
        # This will block until we can get data, in order to skip occational
        # i2c hickups. Ideally, this would include a timeout, althought all
        # we could do then would be to quit.
        while True:
            try:
                return self.bus.read_i2c_block_data(self.address, 0x00)
            except OSError as e:
                print(e)
                time.sleep(.1)
                continue

    # Convert val to signed value
    def twos_complement(self, val, len):
        if (val & (1 << len - 1)):
            val = val - (1 << len)
        return val

    # Convert two bytes from data starting at offset to signed word
    def convert_sw(self, data, offset):
        if self.big_endian:
            return self.twos_complement(data[offset    ] << 8 |
                                        data[offset + 1]       , 16)
        else:
            return self.twos_complement(data[offset    ]      |
                                        data[offset + 1] << 8  , 16)

    def ready(self):
        status = self.__read__(self.STATUS)
        # print("ready: " + str(status))
        return status & self.STATUS_DRDY

    def init(self):
        # initialization has to happen in child classes due to too many
        # differences between QMC and HMC
        pass

    def extract_data(self, raw):
        # extract x,y,z values of magnetic induction from raw data
        data = dict()
        data['x'] = self.convert_sw(raw, self.OFFSET_X)
        data['y'] = self.convert_sw(raw, self.OFFSET_Y)
        data['z'] = self.convert_sw(raw, self.OFFSET_Z)
        # calculate value of B independent of direction
        data['b'] = math.sqrt(
            float(data['x'] * data['x']) +
            float(data['y'] * data['y']) +
            float(data['z'] * data['z']))
        return data

    def _read(self):
        raise(NotImplementedError("_read() has to be implemented by child classes."))

    def read(self):
        self.old_state = self.trigger_state
        data = self._read()
        data['triggered'] = 0

        # print(data['b'])
        if   data['b'] > self.trigger_level + self.trigger_hyst:
            self.trigger_state = 1
        elif data['b'] < self.trigger_level - self.trigger_hyst:
            self.trigger_state = 0

        # avoid triggers because we just started
        if self.just_started:
            self.just_started = False
            self.old_state = self.trigger_state

        if self.old_state == 0 and self.trigger_state == 1:
            data['triggered'] = 1

        return data

class QMCClient(XMCClient):
    # Register numbers
    X_LSB  = 0x00
    STATUS = 0x06
    CONFIG = 0x09
    RESET  = 0x0B

    # Bit values for the STATUS register
    STATUS_DRDY = 1
    STATUS_OVL  = 2
    STATUS_DOR  = 4

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

    # overwriting parent class variables
    name          = "QMC5883"
    address       = 0x1d
    trigger_hyst  = 2000
    big_endian    = False
    OFFSET_X      = 0
    OFFSET_Y      = 2
    OFFSET_Z      = 4

    def init(self):
        # reset device
        self.write(self.RESET, 0x01)
        time.sleep(1)
        # init continous mode
        self.write(self.CONFIG, self.CONFIG_CONTINUOUS
                   | self.CONFIG_50HZ
                   | self.CONFIG_8GAUSS
                   | self.CONFIG_OS512)

    def _read(self):
        while not self.ready():
            time.sleep(0.1)
            print("waiting for DRDY")

        # read data from QMC5883
        raw = []
        for i in range(0, 6):
            raw.append(self.__read__(i))
        data = self.extract_data(raw)
        return data

class HMCClient(XMCClient):
    # Register numbers
    CONFIGA = 0x00
    CONFIGB = 0x01
    CONFIGM = 0x02
    DATA    = 0x03
    STATUS  = 0x09

    # Bit values for the STATUS register
    STATUS_DRDY = 1

    # Range values for the CONFIG register
    CONFIG_GAUSS = {
      0.88: {"reg": 0b000, "gain": 1370},
      1.3 : {"reg": 0b001, "gain": 1090},
      1.9 : {"reg": 0b010, "gain":  820},
      2.5 : {"reg": 0b011, "gain":  660},
      4.0 : {"reg": 0b100, "gain":  440},
      4.7 : {"reg": 0b101, "gain":  390},
      5.6 : {"reg": 0b110, "gain":  330},
      8.1 : {"reg": 0b111, "gain":  230},
      }

    # Rate values for the CONFIG register
    CONFIG_HZ = {
       0.75: 0b000,
       1.5 : 0b001,
       3   : 0b010,
       7.5 : 0b011,
      15   : 0b100,
      30   : 0b101,
      75   : 0b110,
    }

    # Numbers of samples averaged
    CONFIG_AVG = {
      1: 0b00,
      2: 0b01,
      4: 0b10,
      8: 0b11,
    }

    # Mode values for the CONFIG register
    CONFIG_CONTINUOUS = 0b00;

    # overwriting parent class variables
    name          = "HMC5883"
    address       = 0x1e
    trigger_hyst  = 100
    big_endian    = True
    OFFSET_X      = DATA + 0
    OFFSET_Y      = DATA + 4
    OFFSET_Z      = DATA + 2

    def init(self):
        # configure device
        self.write(self.CONFIGA, self.CONFIG_AVG[8] << 5 |
                                 self.CONFIG_HZ[15] << 2)
        self.write(self.CONFIGB, self.CONFIG_GAUSS[8.1]["reg"] << 5)
        self.write(self.CONFIGM, self.CONFIG_CONTINUOUS)
        while not self.ready():
            time.sleep(0.1)
            print("waiting for DRDY")

    def _read(self):
        # read data from HMC5883
        raw = self.__read_block__()
        data = self.extract_data(raw)
        return data
