from Behavior import *
from Stimulus import *
import time, numpy


class Experiment:
    """ this class handles the response to the licks
    """
    def __init__(self, logger, timer, params):
        self.logger = logger
        self.air_dur = params['airpuff_duration']
        self.timeout = params['timeout_duration']
        self.silence = params['silence_thr']
        self.ready_wait = params['init_duration']
        self.trial_wait = params['delay_duration']
        self.randomization = params['randomization']
        self.timer = timer
        self.reward_probe = []
        self.conditions = []
        self.probes = []
        self.post_wait = 0
        self.indexes = []
        self.beh = self.get_behavior()(logger, params)
        self.stim = eval(params['stim_type'])(logger, self.beh)
        self.probe_bias = numpy.repeat(numpy.nan, 1)   # History term for bias calculation

    def prepare(self):
        """Prepare things before experiment starts"""
        self.stim.setup()

    def run(self):
        return self.logger.get_setup_state() == 'running'

    def pre_trial(self):
        """Prepare things before trial starts"""
        self.stim.init_trial()  # initialize stimulus
        self.logger.ping()
        return False

    def trial(self):
        """Do stuff in trial, returns break condition"""
        self.stim.present_trial()  # Start Stimulus
        return False

    def post_trial(self):
        """Handle events after trial ends"""
        self.stim.stop_trial()  # stop stimulus

    def inter_trial(self):
        """Handle intertrial period events"""
        pass

    def on_hold(self, status=False):
        """Handle events that happen in between experiments"""
        pass

    def cleanup(self):
        self.beh.cleanup()

    def get_behavior(self):
        return DummyProbe  # default is raspberry pi

    def _get_new_cond(self):
        """Get curr condition & create random block of all conditions
        Should be called within init_trial
        """
        if self.randomization == 'block':
            if numpy.size(self.indexes) == 0:
                self.indexes = numpy.random.permutation(numpy.size(self.conditions))
            cond = self.conditions[self.indexes[0]]
            self.indexes = self.indexes[1:]
            return cond
        elif self.randomization == 'random':
            return numpy.random.choice(self.conditions)
        elif self.randomization == 'bias':
            if len(self.probe_bias) == 0 or numpy.all(numpy.isnan(self.probe_bias)):
                self.probe_bias = numpy.random.choice(self.probes, 5)
                print('Initializing probe bias!')
                return numpy.random.choice(self.conditions)
            else:
                mn = numpy.min(self.probes)
                mx = numpy.max(self.probes)
                bias_probe = numpy.random.binomial(1, 1 - numpy.nanmean((self.probe_bias - mn)/(mx-mn)))*(mx-mn) + mn
                return numpy.random.choice(self.conditions[self.probes == bias_probe])


class MultiProbe(Experiment):
    """2AFC & GoNOGo tasks with lickspout"""

    def __init__(self, logger, timer, params):
        self.post_wait = 0
        self.responded = False
        super(MultiProbe, self).__init__(logger, timer, params)

    def prepare(self):
        self.conditions, self.probes = self.logger.log_conditions(self.stim.get_condition_table())  # log conditions
        self.stim.setup()
        self.stim.prepare(self.conditions)  # prepare stimulus

    def pre_trial(self):
        cond = self._get_new_cond()
        self.stim.init_trial(cond)
        self.reward_probe = (RewardCond() & self.logger.session_key & dict(cond_idx=cond)).fetch1('probe')
        self.beh.is_licking()
        return False

    def trial(self):
        self.stim.present_trial()  # Start Stimulus
        probe = self.beh.is_licking()
        if probe > 0 and not self.responded:
            self.responded = True
            self.probe_bias = np.concatenate((self.probe_bias[1:], [probe])) # bias correction
            if self.reward_probe == probe:
                print('Correct!')
                self.reward(probe)
                self.timer.start()
                while self.timer.elapsed_time() < 1000:  # give an extra second to associate the reward with stimulus
                    self.stim.present_trial()
                return True
            else:
                print('Wrong!')
                self.punish(probe)
                return True  # break trial
        else:
            return False

    def post_trial(self):
        self.stim.stop_trial()  # stop stimulus when timeout
        self.responded = False
        self.timer.start()
        if self.post_wait > 0:
            self.stim.unshow([0, 0, 0])
        while self.timer.elapsed_time()/1000 < self.post_wait and self.logger.get_setup_state() == 'running':
            time.sleep(0.5)
        self.post_wait = 0
        self.stim.unshow()

    def inter_trial(self):
        if self.beh.is_licking():
            self.timer.start()
        elif self.beh.inactivity_time() > self.silence and self.logger.get_setup_state() == 'running':
            self.logger.update_setup_state('sleeping')
            self.stim.unshow([0, 0, 0])
            self.probe_bias = numpy.repeat(numpy.nan, 1)  # reset bias
            while not self.beh.is_licking() and self.logger.get_setup_state() == 'sleeping':
                self.logger.ping()
                time.sleep(1)
            self.stim.unshow()
            if self.logger.get_setup_state() == 'sleeping':
                self.logger.update_setup_state('running')
                self.timer.start()

    def punish(self, probe):
        self.beh.punish_with_air(probe, self.air_dur)
        self.post_wait = self.timeout

    def reward(self, probe):
        self.beh.water_reward(probe)


class FreeWater(Experiment):
    """Reward upon lick"""

    def trial(self):
        self.stim.present_trial()  # Start Stimulus
        probe = self.beh.is_licking()
        if probe:
            self.beh.water_reward(probe)
            return True
        else:
            return False

    def get_behavior(self):
        return RPBehavior


class PassiveMatlab(Experiment):
    """ Passive Matlab stimulation
    """
    def __init__(self, logger, timer, params):
#        self.stim = eval(params['stim_type'])(logger, self.get_behavior())
        super(PassiveMatlab, self).__init__(logger, timer, params)

    def prepare(self):
        self.stim.setup()
        self.stim.prepare()  # prepare stimulus

    def pre_trial(self):
        self.stim.init_trial()  # initialize stimulus
        return False

    def trial(self):
        return self.stim.trial_done()

    def run(self):
        return self.logger.get_setup_state() == 'stimRunning' and not self.stim.stimulus_done()

    def cleanup(self):
        self.beh.cleanup()
        self.stim.cleanup()
        self.stim.close()


class PassiveMatlabReward(PassiveMatlab):
    """ Passive Matlab with reward in between scans"""

    def on_hold(self, status=True):
        if not status:  # remove probe
            self.beh.get_off_position()
        else:
            self.beh.get_in_position()
            probe = self.beh.is_licking()
            if probe == 1:
                self.beh.water_reward(1)

    def get_behavior(self):
        return TPBehavior


class ActiveMatlab(Experiment):
    """ Rewarded conditions with Matlab
    """
    def __init__(self, logger, timer, params):
        self.stim = eval(params['stim_type'])(logger, self.get_behavior())
        super(ActiveMatlab, self).__init__(logger, timer, params)

    def prepare(self):
        self.stim.setup()
        self.stim.prepare()  # prepare stimulus

    def pre_trial(self):
        self.stim.init_trial()  # initialize stimulus
        self.reward_probe = self.stim.mat.stimulus.get_reward_probe(self, self.logger.get_trial_key())
        self.beh.is_licking()
        return False

    def trial(self):
        probe = self.beh.is_licking()
        if probe > 0:
            if self.reward_probe == probe:
                print('Correct!')
                self.reward(probe)
        return self.stim.trial.done()

    def get_behavior(self):
        return SerialProbe

    def run(self):
        return self.logger.get_setup_state() == 'stimRunning' and not self.stim.stimulus_done()

    def reward(self, probe):
        self.beh.water_reward(probe)

    def cleanup(self):
        self.beh.cleanup()
        self.stim.cleanup()
        self.stim.close()


class CenterPort(Experiment):
    """2AFC with center init position"""

    def __init__(self, logger, timer, params):
        self.post_wait = 0
        self.resp_ready = False
        self.wait_time = Timer()
        super(CenterPort, self).__init__(logger, timer, params)

    def prepare(self):
        self.conditions, self.probes = self.logger.log_conditions(self.stim.get_condition_table())  # log conditions
        self.stim.setup()
        self.stim.prepare(self.conditions)  # prepare stimulus

    def pre_trial(self):
        cond = self._get_new_cond()
        self.reward_probe = (RewardCond() & self.logger.session_key & dict(cond_idx=cond)).fetch1('probe')
        is_ready, ready_time = self.beh.is_ready()
        self.wait_time.start()
        while self.logger.get_setup_state() == 'running' and (not is_ready or ready_time < self.ready_wait):
            time.sleep(.02)
            if self.wait_time.elapsed_time() > 5000:  # ping every 5 seconds
                self.logger.ping()
                self.wait_time.start()
            is_ready, ready_time = self.beh.is_ready()  # update times

        if self.logger.get_setup_state() == 'running':
            print('Starting trial! Yes!')
            self.stim.init_trial(cond)
            self.beh.is_licking()
            self.timer.start()  # trial start counter
            return False
        else:
            return True

    def trial(self):
        if self.logger.get_setup_state() != 'running':
            return True
        self.stim.present_trial()  # Start Stimulus
        probe = self.beh.is_licking()

        # delayed response
        is_ready, ready_time = self.beh.is_ready()  # update times
        if self.timer.elapsed_time() > self.trial_wait and not self.resp_ready:
            self.resp_ready = True
        elif not is_ready and not self.resp_ready:
            print('Wrong!')
            self.punish(probe)
            return True  # break trial

        # response to probe lick
        if probe > 0 and self.resp_ready:
            if self.reward_probe != probe:
                print('Wrong!')
                self.punish(probe)
            else:
                print('Correct!')
                self.reward(probe)
            self.probe_bias = np.concatenate((self.probe_bias[1:], [probe]))
            self.resp_ready = False
            return True  # break trial
        else:
            return False

    def post_trial(self):
        self.stim.stop_trial()  # stop stimulus when timeout
        self.timer.start()
        if self.post_wait > 0:
            self.stim.unshow([0, 0, 0])
        while self.timer.elapsed_time()/1000 < self.post_wait and self.logger.get_setup_state() == 'running':
            time.sleep(0.5)
        self.post_wait = 0
        self.stim.unshow()

    def inter_trial(self):
        if self.beh.is_licking():
            self.timer.start()

    def get_behavior(self):
        return RPBehavior

    def punish(self, probe):
        self.post_wait = self.timeout

    def reward(self, probe):
        self.beh.water_reward(probe)


class DummyCenterPort(CenterPort):
    def get_behavior(self):
        return DummyProbe


class CenterPortTrain(CenterPort):
    """Training on the 2AFC with center init position"""

    def trial(self):
        if self.logger.get_setup_state() != 'running':
            return True
        probe = self.beh.is_licking()

        # delayed response
        is_ready, ready_time = self.beh.is_ready()  # update times
        if self.timer.elapsed_time() > self.trial_wait and not self.resp_ready:
            self.resp_ready = True
        elif not is_ready and not self.resp_ready:
            print('Wrong!')
            self.punish(probe)
            return True  # break trial

        # response to probe lick
        if probe > 0 and self.resp_ready:
            print('Correct!')
            self.reward(probe)
            self.resp_ready = False
            return True  # break trial
        else:
            return False

