# -*- coding: utf-8 -*-
# This file is part of Teres.
#
# Copyright (C) 2016 Peter Kotvan
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
"""
Python library for reporting test results providing API for usage of multiple
handlers. In it's core it's highly inspired byt implementation fo python logging
module.
"""

import os
import atexit

# These are default test results and their values. This should be reset to 0
# after particular test is finished.

FILE = 99
ERROR = 50
FAIL = 40
PASS = 30
INFO = 20
DEBUG = 10
NONE = 0

# used in cleanup function
_PID = os.getpid()


def result_to_name(result):
    """
    Translate reporter result to string.
    """
    mapping = {
        ERROR: "ERROR",
        FAIL: "FAIL",
        PASS: "PASS",
        FILE: "FILE",
        INFO: "INFO",
        DEBUG: "DEBUG",
        NONE: "NONE",
    }

    return mapping[result]


@atexit.register
def cleanup():
    """
    Cleanup method.
    """
    # when somebody uses fork() and the process ends, don't do anything,
    # since this is handled by parent process
    if _PID != os.getpid():
        return
    Reporter.get_reporter().test_end(clean_end=False)


class HandlerError(Exception):
    """
    Generic exception for handlers.
    """
    pass


class ReportRecord(object):
    """
    ReportRecord instance represents and evet being logged.
    """

    def __init__(self,
                 result,
                 msg=None,
                 logfile=None,
                 logname=None,
                 flags=None):
        super(ReportRecord, self).__init__()
        self.result = result
        self.msg = msg
        self.logfile = logfile
        self.logname = logname
        if flags is None:
            flags = {}
        self.flags = flags


class Reporter(object):
    """
    Class handling handlers for reporting. Implementing basic API.
    """

    _instance = None

    @staticmethod
    def get_reporter():
        """
        Return an instance of this class. The instance is the same with each
        call thus cereating a singleton.
        """
        if Reporter._instance is None:
            Reporter._instance = Reporter()

        return Reporter._instance

    def __init__(self):
        super(Reporter, self).__init__()
        self.overall_result = NONE
        self.handlers = []
        self.finished = False

    def __del__(self):
        if not self.finished:
            self.test_end()

    def test_end(self, clean_end=True):
        """
        Flush all results and clean up.
        """
        if not clean_end:
            self.log_error("Test ended unexpectedly.")

        self.finished = True
        for handler in self.handlers:
            handler.close()

        self.handlers = []

    def log(self, result, msg, flags=None):
        """
        Log a message with specific level.
        """
        if FILE > result >= PASS:
            self.overall_result = max(self.overall_result, result)
            self._log(result, msg, flags=flags)

    def log_error(self, msg, flags=None):
        """
        Log an ERROR message.
        """
        self.overall_result = max(self.overall_result, ERROR)
        self._log(ERROR, msg, flags=flags)

    def log_fail(self, msg, flags=None):
        """
        Log a FAIL message.
        """
        self.overall_result = max(self.overall_result, FAIL)
        self._log(FAIL, msg, flags=flags)

    def log_pass(self, msg, flags=None):
        """
        Log a PASS message.
        """
        self.overall_result = max(self.overall_result, PASS)
        self._log(PASS, msg, flags=flags)

    def log_info(self, msg, flags=None):
        """
        Log INFO message.
        """
        self._log(INFO, msg, flags=flags)

    def log_debug(self, msg, flags=None):
        """
        Log DEBUG message.
        """
        self._log(DEBUG, msg, flags=flags)

    def send_file(self, logfile, logname=None, msg=None, flags=None):
        """
        Send log file.
        """
        self._log(FILE, msg=msg, logfile=logfile, logname=logname, flags=flags)

    def _log(self, result, msg, **kwargs):
        """
         Low level logging routine.
        """
        record = ReportRecord(result, msg, **kwargs)

        self.call_handlers(record)

    def add_handler(self, handler):
        """
        Add the specified handler to this reporter.
        """
        if self.finished:
            raise Exception("Cannot add handler if the test ended.")
        if handler not in self.handlers:
            self.handlers.append(handler)

    def remove_handler(self, handler):
        """
        Remove the specified handler from this reporter.
        """
        if handler in self.handlers:
            self.handlers.remove(handler)

    def call_handlers(self, record):
        """
        Pass the record to all registered handlers.
        """
        for handler in self.handlers:
            handler.emit(record)


class Handler(object):
    """
    Class defining the Handler API.
    """

    def __init__(self, result_level=INFO, process_logs=True):
        super(Handler, self).__init__()
        self._result_level = result_level
        self._process_logs = process_logs

    @property
    def result_level(self):
        """
        Result level getter.
        """
        return self._result_level

    @result_level.setter
    def result_level(self, result_level):
        """
        Result level setter.
        """
        self._result_level = result_level

    @property
    def process_logs(self):
        """
        Getter for process_logs.
        """
        return self._process_logs

    @process_logs.setter
    def process_logs(self, value):
        """
        Set process_logs.
        """
        self._process_logs = value

    def emit(self, record):
        """
        Decides if we are reporting a result or a file and executes the correct
        routine.
        """
        # Check default level and other tocnditions.
        if record.result < self.result_level:
            return

        if (record.result == FILE) and not self.process_logs:
            return

        if (record.result == FILE) and (record.logfile is not None):
            return self._emit_file(record)

        if record.msg is None:
            return

        self._emit_log(record)

    def _emit_log(self, record):
        """
        Method taking care of handling messages.
        """
        raise NotImplementedError

    def _emit_file(self, record):
        """
        Method taking care of handling file records.
        """
        raise NotImplementedError

    def close(self):
        """
        This method should flush all outstanding results and logs.
        """
        raise NotImplementedError
