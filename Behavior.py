from LickSpout import *
from Timer import *
import pygame


class Behavior:
    """ This class handles the behavior variables """
    def __init__(self, logger, params):
        self.resp_int = params['response_interval']
        self.resp_timer = Timer()
        self.resp_timer.start()
        self.logger = logger

    def is_licking(self):
        return False

    def is_ready(self):
        return False, 0

    def water_reward(self, probe):
        print('Giving Water at probe:%1d' % probe)

    def punish_with_air(self, probe, air_dur=200):
        print('Punishing with Air at probe:%1d' % probe)

    def give_odor(self, delivery_probe, odor_idx, odor_dur, odor_dutycycle):
        print('Odor %1d presentation for %d' % (odor_idx, odor_dur))

    def inactivity_time(self):  # in minutes
        return 0

    def cleanup(self):
        pass

    def get_in_position(self):
        pass

    def get_off_position(self):
        pass


class RPBehavior(Behavior):
    """ This class handles the behavior variables for RP """
    def __init__(self, logger, params):
        self.probe = RPProbe(logger)
        super(RPBehavior, self).__init__(logger, params)

    def is_licking(self):
        probe = self.probe.lick()
        time_since_last_lick = self.resp_timer.elapsed_time()
        if time_since_last_lick < self.resp_int:
            probe = 0
        # reset lick timer if licking is detected &
        if probe > 0:
            #print(self.resp_timer.elapsed_time())
            self.resp_timer.start()
        return probe

    def is_ready(self):
        ready, ready_time = self.probe.in_position()
        return ready, ready_time

    def water_reward(self, probe):
        self.probe.give_liquid(probe)

    def punish_with_air(self, probe, air_dur=200):
        self.probe.give_air(probe, air_dur)

    def give_odor(self, delivery_probe, odor_idx, odor_dur, odor_dutycycle):
        self.probe.give_odor(delivery_probe, odor_idx, odor_dur, odor_dutycycle)

    def inactivity_time(self):  # in minutes
        return numpy.minimum(self.probe.timer_probe1.elapsed_time(),
                             self.probe.timer_probe2.elapsed_time()) / 1000 / 60

    def cleanup(self):
        self.probe.cleanup()


class TPBehavior(RPBehavior):
    def __init__(self, logger, params):
        self.probe = SerialProbe(logger)
        super(RPBehavior, self).__init__(logger, params)

    def get_in_position(self):
        self.probe.get_in_position()

    def get_off_position(self):
        self.probe.get_off_position()

    def is_ready(self):
        ready = self.probe.in_position()
        return ready, 0


class DummyProbe(Behavior):
    def __init__(self, logger, params):
        self.lick_timer = Timer()
        self.lick_timer.start()
        self.ready_timer = Timer()
        self.ready_timer.start()
        self.ready = False
        super(DummyProbe, self).__init__(logger, params)

    def is_ready(self):
        self.__get_events()
        eltime = self.ready_timer.elapsed_time()
        return self.ready, eltime

    def inactivity_time(self):  # in minutes
        return self.lick_timer.elapsed_time() / 1000 / 60

    def __get_events(self):
        probe = 0
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    self.logger.log_lick(1)
                    probe = 1
                    self.lick_timer.start()
                elif event.key == pygame.K_RIGHT:
                    self.logger.log_lick(2)
                    probe = 2
                elif event.key == pygame.K_SPACE and self.ready:
                    self.ready = False
                    print('off position')
                elif event.key == pygame.K_SPACE and not self.ready:
                    self.lick_timer.start()
                    self.ready = True
                    print('in position')
        return probe



