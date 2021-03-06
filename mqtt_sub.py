__author__ = "madawood"

# !/usr/bin/python
# mqtt demo on Raspberry Pi 3 using Sain Smart or Adafruit 16x2 LCD and button module
# Author madawood using Open Source components
# Version 1.3  --- January 11, 2017
# This is the LCD message subscriber thread.

import time
import threading
import signal
import json
import logging
import paho.mqtt.client as mqtt
from subprocess import *

from dweet import Dweet
from cloud import Cloud
import time

logger = logging.getLogger("mqtt_app")
data = {}


def _sleep_handler(signum, frame):
    print "SIGINT Received. Stopping app"
    raise KeyboardInterrupt


def _stop_handler(signum, frame):
    print "SIGTERM Received. Stopping app"
    raise KeyboardInterrupt


class MqttSub(threading.Thread):
    def __init__(self, enabled, host, port, topics, timeout=5):
        threading.Thread.__init__(self)
        self.enabled = enabled
        self.stop_event = threading.Event()
        self.setDaemon(True)
        self.host = host
        self.port = port
        self.topics = topics
        self.timeout = timeout
        self.data_changed = False
        logger.debug("Mqtt subscription instance is successfully initialized!")

    def on_connect(self, client, userdata, flags, rc):
        logger.debug("SUB: Connected with result code :%s" % (str(rc)))
        client.subscribe(str(userdata))

    def on_message(self, client, userdata, msg):
        logger.debug("SUB: Payload from : %s" % userdata)
        logger.debug("SUB: Payload is : %s" % msg.payload)
        payload = msg.payload
        payload = payload.replace("'", "\"")
        global data
        try:
            payload = json.loads(payload)
        except ValueError:
            logger.info("Given payload is not in json format!")
        if userdata == "wx":
            data["Temperature"] = payload[0]
            data["Humidity"] = payload[1]
            data["Pressure"] = payload[2]
        elif userdata == "geo":
            data["Latitude"] = payload[0]
            data["Longitude"] = payload[1]
        elif userdata == "buttons":
            data["Key"] = payload[0]
        self.data_changed = True
        # data = {str(userdata): json.loads(paylaod)}
        #client.disconnect()

    def publish_data(self, data):
        logger.debug("Sub: Publishing the data to upstream!")
        dweet = Dweet.get_instance()
        if dweet:
            dweet.dweet(data)
        cloud = Cloud.get_instance()
        if cloud:
            cloud.send_to_cloud(data)

    def run(self):
        global data
        if self.enabled:
            logger.debug("Started the subscription thread!")
            try:
                clients = []
                for topic in self.topics:
                    client = mqtt.Client(clean_session=True, userdata=topic)
                    client.connect(self.host, port=int(self.port), keepalive=60)
                    client.message_callback_add(topic, self.on_message)
                    client.loop_start()
                    client.subscribe(topic)
                    clients.append(client)
                while True:
                    if data and self.data_changed:
                        self.publish_data(data)
                        self.data_changed = False
                        if self.stop_event.is_set():
                            logger.debug("Sub: exiting from thread, as stop event is set!")
                            self.stop_event.clear()
                            for cli in clients:
                                cli.loop_stop()
                            break
            except Exception as ex:
                logger.exception("Error in subscription:%s" % str(ex))
        else:
            logger.info("Sub: subscriber is disabled, so not starting thread!")

    def close(self):
        logger.debug("Sub: stop event is set!")
        self.stop_event.set()


if __name__ == "__main__":
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    logger.setLevel(10)
    console = logging.StreamHandler()
    console.setLevel(10)
    console.setFormatter(formatter)
    logger.addHandler(console)

    signal.signal(signal.SIGTERM, _stop_handler)
    signal.signal(signal.SIGINT, _sleep_handler)
    m = MqttSub(True, "localhost", 1883, ["wx", "geo", "buttons"])
    m.start()
    while True:
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            m.close()
            print "App closed"
            break
        except Exception as ex:
            print("Caught exception! Terminating..")
