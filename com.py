import serial
import time
from utils import us_to_ticks, ticks_to_us, pack_channels, crc_transmit


class communication():

    def __init__(self, com_port):
        self.ser = serial.Serial(com_port, baudrate=416666, timeout=0)
        self.payload = []
        self.crc = []
        self.message = []
        self.t1 = 0
        self.received_bytes = None

    def transmit(self):
        self.t1 = time.time()
        read = False
        while True:
            t2 = time.time()
            dt = (t2-self.t1)*1000.0  # delta t in milliseconds

            # handle read buffer after telemetry is received (i.e. after 3ms for 150Hz(:6.67ms))
            if 3 < dt and not read:
                waiting = self.ser.in_waiting
                data = self.ser.read(waiting)
                if data != b'':
                    self.received_bytes = data
                read = True

            # write new frame
            if dt >= 6.666667:
                self.t1 = time.time()
                read = False
                self.ser.write(bytearray(self.message))

    def decode_telemetry(self):
        while True:
            if self.received_bytes is not None:
                rcv_list = list(self.received_bytes)
                # each received list must hold transmitted frame(26 bytes) and telemetry, so should be larger
                possible_telemetry_indices = [i for i, x in enumerate(rcv_list) if x == 234] # 234 = b'\ea'
                for i in possible_telemetry_indices:
                    telemetry_list = rcv_list[i:]
                    # check if address byte is correct
                    tel_type = telemetry_list[2]
                    if tel_type == 8:  # 0x08: battery sensor
                        # int16_t voltage (100*mV)
                        # int16_t current (100*mA)
                        # int24_t capacity used (mAh)
                        # int8_t battery remaining (percent)
                        voltage = int.from_bytes(bytearray(telemetry_list[3:5]), "big")
                        print(f'voltage: {voltage}')
            time.sleep(0.0001)

    def update_data(self, channels_pwm):
        # convert pwm values to rc values
        channels_rc = us_to_ticks(channels_pwm)

        # pack 16 channels to 22 bytes
        packed_channel = pack_channels(channels_rc)

        # calculate crc
        crc = crc_transmit([0x16], packed_channel)
        crc = [int(crc, 16)]

        self.payload = packed_channel
        self.crc = crc
        self.message = [0xee, 0x18, 0x16] + self.payload + self.crc

    def update_telemetry(self):
        # calculate crc
        # uplink_RSSI_1/uplink_RSSI_2/uplink_Link_quality/uplink_SNR/active_antenna/rf_Mode/uplink_TX_Power/downlink_RSSI/downlink_Link_quality/downlink_SNR
        # telemetry = [0x5A, 0x5A, 0x5A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        telemetry = [0x05, 0x05, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        crc = crc_transmit([0xC], telemetry)
        crc = [int(crc, 16)]

        self.payload = telemetry
        self.crc = crc
        # [CRSF_ADDRESS_RADIO_TRANSMITTER = 0xEE] [LinkStatisticsFrameLength + 2 = 12] [CRSF_FRAMETYPE_LINK_STATISTICS = 0x14]
        self.message = [0xee, 0x0C, 0x14] + self.payload + self.crc
