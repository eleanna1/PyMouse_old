from Database import *
from time import sleep
import numpy, socket
from Timer import *
from concurrent.futures import ThreadPoolExecutor
from importlib import util
from ThreadWorker import GetHWPoller
import serial
import sys
import platform


class Probe:
    def __init__(self, logger):
        self.logger = logger
        self.probe1 = False
        self.probe2 = False
        self.ready = False
        self.timer_probe1 = Timer()
        self.timer_probe2 = Timer()
        self.timer_ready = Timer()
        self.__calc_pulse_dur(logger.reward_amount)
        self.thread = ThreadPoolExecutor(max_workers=1)

    def give_air(self, probe, duration, log=True):
        pass

    def give_liquid(self, probe, duration=False, log=True):
        pass

    def give_odor(self, odor_idx, duration, log=True):
        pass

    def lick(self):
        if self.probe1:
            self.probe1 = False
            probe = 1
            #print('Probe 1 activated')
        elif self.probe2:
            self.probe2 = False
            probe = 2
            #print('Probe 2 activated')
        else:
            probe = 0
        return probe

    def probe1_licked(self, channel):
        self.probe1 = True
        self.timer_probe1.start()
        self.logger.log_lick(1)
        #print('Probe 1 activated')

    def probe2_licked(self, channel):
        self.probe2 = True
        self.timer_probe2.start()
        self.logger.log_lick(2)
        #print('Probe 2 activated')

    def in_position(self):
        return True, 0

    def get_in_position(self):
        pass

    def get_off_position(self):
        pass

    def __calc_pulse_dur(self, reward_amount):  # calculate pulse duration for the desired reward amount
        self.liquid_dur = dict()
        probes = (LiquidCalibration() & dict(setup=self.logger.setup)).fetch('probe')
        for probe in list(set(probes)):
            key = dict(setup=self.logger.setup, probe=probe)
            dates = (LiquidCalibration() & key).fetch('date', order_by='date')
            key['date'] = dates[-1]  # use the most recent calibration
            pulse_dur, pulse_num, weight = (LiquidCalibration.PulseWeight() & key).fetch('pulse_dur',
                                                                                         'pulse_num',
                                                                                         'weight')
            self.liquid_dur[probe] = numpy.interp(reward_amount,
                                                  numpy.divide(weight, pulse_num),
                                                  pulse_dur)

    def cleanup(self):
        pass


class RPProbe(Probe):
    def __init__(self, logger):
        super(RPProbe, self).__init__(logger)
        from RPi import GPIO
        self.setup = int(''.join(list(filter(str.isdigit, socket.gethostname()))))
        self.GPIO = GPIO
        self.GPIO.setmode(self.GPIO.BOARD)
        self.GPIO.setup([11, 13, 21], self.GPIO.IN)
        self.GPIO.setup([15, 16, 18, 22], self.GPIO.OUT, initial=self.GPIO.LOW)
        self.channels = {'air': {1: 18, 2: 22},
                         'liquid': {1: 15, 2: 16},
                         'lick': {1: 11, 2: 13},
                         'start': {1: 21}}  # 2
        self.frequency = 20
        self.GPIO.add_event_detect(self.channels['lick'][2], self.GPIO.RISING, callback=self.probe2_licked, bouncetime=200)
        self.GPIO.add_event_detect(self.channels['lick'][1], self.GPIO.RISING, callback=self.probe1_licked, bouncetime=200)
        self.GPIO.add_event_detect(self.channels['start'][1], self.GPIO.BOTH, callback=self.position_change, bouncetime=50)

    def give_air(self, probe, duration, log=True):
        self.thread.submit(self.__pulse_out, self.channels['air'][probe], duration)
        if log:
            self.logger.log_air(probe)

    def give_liquid(self, probe, duration=False, log=True):
        if not duration:
            duration = self.liquid_dur[probe]
        self.thread.submit(self.__pulse_out, self.channels['liquid'][probe], duration)
        if log:
            self.logger.log_liquid(probe)

    def give_odor(self, odor_idx, duration, dutycycle, log=True):
        #print('Odor %1d presentation for %d' % (odor_idx, duration))
        for idx in range(len(odor_idx)):
            print('Odor %1d presentation for %d' % (idx, dutycycle[idx-1]))
            self.thread.submit(self.__pwd_out, self.channels['air'][odor_idx[idx-1]], duration[idx-1], dutycycle[idx-1])
        if log:
            self.logger.log_odor(odor_idx)

    def position_change(self, channel=0):
        if self.GPIO.input(self.channels['start'][1]):
            self.timer_ready.start()
            self.ready = True
            print('in position')
        else:
            self.ready = False
            print('off position')

    def in_position(self):
        # handle missed events
        ready = self.GPIO.input(self.channels['start'][1])
        if self.ready != ready:
            self.position_change()
        if not self.ready:
            ready_time = 0
        else:
            ready_time = self.timer_ready.elapsed_time()
        return self.ready, ready_time

    def __pwd_out(self, channel, duration, dutycycle):
        pwm = self.GPIO.PWM(channel, self.frequency)
        pwm.ChangeFrequency(self.frequency)
        pwm.start(dutycycle)
        sleep(duration/1000)    # to add a  delay in seconds
        pwm.stop()

    def __pulse_out(self, channel, duration):
        self.GPIO.output(channel, self.GPIO.HIGH)
        sleep(duration/1000)
        self.GPIO.output(channel, self.GPIO.LOW)

    def cleanup(self):
        self.GPIO.remove_event_detect(self.channels['lick'][1])
        self.GPIO.remove_event_detect(self.channels['lick'][2])
        self.GPIO.remove_event_detect(self.channels['start'][1])
        self.GPIO.cleanup()


class SerialProbe(Probe):
    def __init__(self, logger):
        if platform.system() == 'Linux':
            ser_port = '/dev/ttyUSB0'
        else:
            ser_port = '/dev/cu.UC-232AC'
        self.serial = serial.serial_for_url(ser_port)
        self.channels = {'out': {1: 'dtr', 2: 'rts'},
                         'in': {1: 'dsr', 2: 'cts'}}

        self.serial.dtr = False  # probe 1
        self.serial.rts = False  # place probe in position

        setattr(self.serial, self.channels['out'][1], False)  # read a byte from the hardware
        setattr(self.serial, self.channels['out'][2], False)  # read a byte from the hardware

        super(SerialProbe, self).__init__(logger)
        self.worker = GetHWPoller(0.001, self.poll_probe)
        self.interlock = False  # set to prohibit thread from accessing serial port
        self.worker.start()

    def give_liquid(self, probe, duration=False, log=True):
        if not duration:
            duration = self.liquid_dur[probe]
        self.thread.submit(self.__pulse_out, probe, duration)
        if log:
            self.logger.log_liquid(probe)

    def poll_probe(self):
        if self.interlock:
            return "interlock"  # someone else is using serial port, wait till done!
        self.interlock = True  # set interlock so we won't be interrupted
        response1 = getattr(self.serial, self.channels['in'][1])  # read a byte from the hardware
        response2 = getattr(self.serial, self.channels['in'][2])  # read a byte from the hardware
        self.interlock = False
        if response1:
            if self.timer_probe1.elapsed_time() > 200:
                self.probe1_licked(1)
        if response2:
            if self.timer_probe2.elapsed_time() > 200:
                self.probe2_licked(2)

    def __pulse_out(self, probe, duration):
        while self.interlock:  # busy, wait for free, should timeout here
            print("waiting for interlock")
            sys.stdout.flush()
        print('reward!')
        self.interlock = True
        setattr(self.serial, self.channels['out'][probe], True)
        sleep(duration/1000)
        setattr(self.serial, self.channels['out'][probe], False)
        self.interlock = False

    def in_position(self):
        return self.ready

    def cleanup(self):
        self.worker.kill()


class SerialProbeOdor(SerialProbe):
    def __init__(self, logger):
        if platform.system() == 'Linux':
            ser_port = '/dev/ttyUSB0'
        else:
            ser_port = '/dev/cu.UC-232AC'
        self.serial = serial.serial_for_url(ser_port)
        self.serial.dtr = False  # probe 1
        self.serial.rts = False  # place probe in position
        super(SerialProbe, self).__init__(logger)
        self.worker = GetHWPoller(0.001, self.poll_probe)
        self.interlock = False  # set to prohibit thread from accessing serial port
        self.worker.start()

    def give_liquid(self, probe, duration=False, log=True):
        if not duration:
            duration = self.liquid_dur[probe]
        self.thread.submit(self.__pulse_out, duration)
        if log:
            self.logger.log_liquid(probe)

    def poll_probe(self):
        if self.interlock:
            return "interlock"  # someone else is using serial port, wait till done!
        self.interlock = True  # set interlock so we won't be interrupted
        response1 = self.serial.dsr  # read a byte from the hardware
        response2 = self.serial.cts  # read a byte from the hardware
        self.interlock = False
        if response1:
            if self.timer_probe1.elapsed_time() > 200:
                self.probe1_licked(1)
        if response2:
            if self.timer_probe2.elapsed_time() > 200:
                self.probe2_licked(2)

    def __pulse_out(self, duration):
        while self.interlock:  # busy, wait for free, should timeout here
            print("waiting for interlock")
            sys.stdout.flush()
        print('reward!')
        self.interlock = True
        self.serial.dtr = True
        sleep(duration / 1000)
        self.serial.dtr = False
        self.interlock = False

    def get_in_position(self):
        if not self.ready:
            self.serial.rts = True
            self.ready = True

    def get_off_position(self):
        if self.ready:
            self.serial.rts = False
            self.ready = False

    def in_position(self):
        return self.ready

    def cleanup(self):
        self.worker.kill()