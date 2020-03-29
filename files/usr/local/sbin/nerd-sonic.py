#!/usr/bin/python
# --------------------------------------------------------------------------
# Script executed by systemd service nerd-alarmclock.service
#
# Please edit /etc/nerd-alarmclock.conf to configure this script.
#
# Author: Bernhard Bablok
# License: GPL3
#
# Website: https://github.com/bablokb/nerd-alarmclock
#
# --------------------------------------------------------------------------

import os
import sys
import syslog
import signal
import locale
import configparser
import threading

sys.path.append(os.path.abspath('/usr/local/lib/python3.5/site-packages'))
sys.path.append(os.path.abspath('/usr/local/lib/python3.5/site-packages/nsonic/ext'))
from nsonic import Settings, WebThread, Database, SensorsControllerThread, DisplayStateThread

# --- helper class for logging to syslog/stderr   --------------------------

class Msg(object):
    """ Very basic message writer class """

    # --- constructor   ------------------------------------------------------

    def __init__(self, debug):
        """ Constructor """
        self._debug = debug
        self._lock = threading.Lock()
        try:
            if os.getpgrp() == os.tcgetpgrp(sys.stdout.fileno()):
                self._syslog = False
                self._debug = "1"
            else:
                self._syslog = True
        except:
            self._syslog = True

        if self._syslog:
            syslog.openlog("nerd-alarmclock")

    def msg(self, text):
        """ write message to the system log """
        if self._debug == '1':
            with self._lock:
                if self._syslog:
                    syslog.syslog(text)
                else:
                    sys.stderr.write(text)
                    sys.stderr.write("\n")
                    sys.stderr.flush()

# --------------------------------------------------------------------------
# --------------------------------------------------------------------------

class Main():

    def __init__(self):
        self._threads = None
        self._settings = None

        parser = Main._create_parser()
        self._init_objects(parser)

        # setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def run(self):
        # create and start threads
        self._threads = Main._start_threads(self._settings)

        # wait for threads to terminate
        for thread in self._threads:
            thread.join()

    @staticmethod
    def _create_parser():
        # set local to default from environment
        locale.setlocale(locale.LC_ALL, '')

        # read configuration
        parser = configparser.RawConfigParser()
        parser.optionxform = str
        parser.read('/etc/nerd-alarmclock.conf')

        return parser

    def _init_objects(self, parser):
        self._settings = Settings.Settings(parser)
        self._settings.log = Msg(
            self._settings.get_value('GLOBAL', 'debug', 0))
        self._settings.load()

        self._settings.database = Database.Database(self._settings)

    @staticmethod
    def _start_threads(settings):
        """ Start all threads """

        threads = []

        web_thread = WebThread.WebThread(settings)
        threads.append(web_thread)

        sensors_thread = SensorsControllerThread.SensorsControllerThread(settings)
        threads.append(sensors_thread)

        display_thread = DisplayStateThread.DisplayStateThread(settings)
        threads.append(display_thread)

        for thread in threads:
            thread.start()

        return threads

    @staticmethod
    def _stop_threads(settings):
        """ Stop all threads """

        # send event to all threads
        settings.stop_event.set()

    def _signal_handler(self, _signo, _stack_frame):
        """ Signal-handler to cleanup threads """

        self._settings.log.msg("interrupt %d detected, exiting" % _signo)
        Main._stop_threads(self._settings)
        self._settings.save(wait=False)
        sys.exit(0)


if __name__ == "__main__":
    Main().run()
