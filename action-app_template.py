#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from snipsTools import SnipsConfigParser
from hermes_python.hermes import Hermes
from hermes_python.ontology import *
import io

import datetime
import soco
from soco.snapshot import Snapshot
import soco.alarms

CONFIG_INI = "config.ini"

# If this skill is supposed to run on the satellite,
# please get this mqtt connection info from <config.ini>
# Hint: MQTT server is always running on the master device
MQTT_IP_ADDR = "localhost"
MQTT_PORT = 1883
MQTT_ADDR = "{}:{}".format(MQTT_IP_ADDR, str(MQTT_PORT))

class Template(object):
    """Class used to wrap action code with mqtt connection
        
        Please change the name refering to your application
    """

    def __init__(self):
        # get the configuration if needed
        try:
            self.config = SnipsConfigParser.read_configuration_file(CONFIG_INI)
        except :
            self.config = None

        # start listening to MQTT
        self.start_blocking()


    def get_player(self, name):
        players = soco.discover()
        for speaker in players:
            print("%s (%s)" % (speaker.player_name, speaker.ip_address))
            if speaker.player_name.lower().replace('ü', 'u') == name:
                return speaker

    def get_timedelta(self, duration):
        return datetime.timedelta(days = duration.days, hours = duration.hours, minutes = duration.minutes, seconds = duration.seconds)
    
    def remaining_time_str(self, delta):
        result = ''
        add_and = ''
        t = str(delta).split(':')

        if int(float(t[2])) > 0:
            add_and = ' und '
            result += "{} Sekunden".format(int(float(t[2])))

        if int(t[1]) > 0:
            result = "{} Minuten {}{}".format(int(t[1]), add_and, result)
            if add_and != '':
                add_and = ', '
            else:
                add_and = ' und '

        if int(t[0]) > 0:

            result = "{} Stunden{}{}".format(int(t[0]), add_and, result)
        return result
        
    # --> Sub callback function, one per intent
    def intent_1_callback(self, hermes, intent_message):
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "")
        
        # action code goes here...
        print('[Received] intent: {}'.format(intent_message.intent.intent_name))

        device = self.get_player(intent_message.site_id)
        alarm = soco.alarms.Alarm(device)
        alarm.recurrence = "ONCE"
        duration_slot = intent_message.slots.duration.first()
        t = self.get_timedelta(duration_slot)
        print(t)
        alarm.start_time = (datetime.datetime.combine(datetime.date.today(), alarm.start_time) + t).time()
        alarm.save()

        # if need to speak the execution result by tts
        hermes.publish_start_session_notification(intent_message.site_id, "Teimer gestellt auf {}".format(intent_message.slots.duration[0].raw_value), "")

    def intent_2_callback(self, hermes, intent_message):
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "")

        # action code goes here...
        print('[Received] intent: {}'.format(intent_message.intent.intent_name))
        device = self.get_player(intent_message.site_id)
        alarms = soco.alarms.get_alarms(device)
        sortedAlarms = sorted({x for x in alarms if x.enabled}, key=lambda a: a.start_time)
        print(sortedAlarms)

        if len(sortedAlarms) == 0:
            hermes.publish_start_session_notification(intent_message.site_id, "Es läuft gerade kein Teimer", "")
            return
        
        delta = datetime.datetime.combine(datetime.date.today(), sortedAlarms[0].start_time) - datetime.datetime.now()
        print(delta)

        remaining = self.remaining_time_str(delta)
        print(remaining)

        # if need to speak the execution result by tts
        hermes.publish_start_session_notification(intent_message.site_id, remaining, "")

    def intent_3_callback(self, hermes, intent_message):
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "")

        device = self.get_player(intent_message.site_id)
        alarms = soco.alarms.get_alarms(device)
        count = 0
        for alarm in alarms:
            if alarm.recurrence == "ONCE":
                alarm.remove()
                count += 1

        # action code goes here...
        print('[Received] intent: {}'.format(intent_message.intent.intent_name))

        # if need to speak the execution result by tts
        hermes.publish_start_session_notification(intent_message.site_id, "{} teimer wurde{} entfernt".format(count, "" if count == 1 else "n"), "")

    # More callback function goes here...

    # --> Master callback function, triggered everytime an intent is recognized
    def master_intent_callback(self,hermes, intent_message):
        coming_intent = intent_message.intent.intent_name
        if coming_intent == 'mcitar:timerRemember':
            self.intent_1_callback(hermes, intent_message)
        if coming_intent == 'mcitar:timerRemainingTime':
            self.intent_2_callback(hermes, intent_message)
        if coming_intent == 'mcitar:timerRemove':
            self.intent_3_callback(hermes, intent_message)

        # more callback and if condition goes here...

    # --> Register callback function and start MQTT
    def start_blocking(self):
        with Hermes(MQTT_ADDR) as h:
            h.subscribe_intents(self.master_intent_callback).start()

if __name__ == "__main__":
    Template()
