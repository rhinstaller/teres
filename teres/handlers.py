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
Handlers for the teres package.
"""

import logging
import collections
import os.path
import tempfile
import shutil
import teres


def _result_to_level(result):
    """
    Translate reporter result to logging level.
    """
    mapping = {
        teres.FILE: logging.INFO,
        teres.ERROR: logging.CRITICAL,
        teres.FAIL: logging.ERROR,
        teres.PASS: logging.INFO,
        teres.INFO: logging.INFO,
        teres.DEBUG: logging.DEBUG,
        teres.NONE: logging.NOTSET,
    }

    return mapping[result]


class LoggingHandler(teres.Handler):
    """
    A handler class which writes the test results to a file.
    """

    def __init__(self, name, handlers, result=teres.INFO, dest="/tmp/"):
        super(LoggingHandler, self).__init__(result)

        self.name = name
        self.dest = dest
        self.logdir = tempfile.mkdtemp(prefix=self.name, dir=self.dest)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(_result_to_level(self.result))

        if not isinstance(handlers, collections.Iterable):
            handlers = [handlers]

        for handler in handlers:
            self.logger.addHandler(handler)

    def _emit_log(self, record):
        self.logger.log(
            _result_to_level(record.result), self._format_msg(record))

    def _emit_file(self, record):
        if record.logname is None:
            record.logname = os.path.basename(record.logfile).replace(' ', '_')

        if record.msg is None:
            record.msg = "Copying {} to: {}".format(
                record.logfile, self.logdir + "/" + record.logname)

        shutil.copy(record.logfile, self.logdir + "/" + record.logname)

        self.logger.log(
            _result_to_level(record.result), self._format_msg(record))

    def _format_msg(self, record):
        """
        Method that takes care of formatting a message.
        """
        res = teres.result_to_name(record.result)
        spaces = 10 - 3 - len(res)

        head = ":: [   " + res + " " * spaces + "] :: "

        return head + record.msg

    def close(self):
        """
        LoggingHandler does not need cleanup but it's called by Reporter in
        destructor.
        """
        pass
