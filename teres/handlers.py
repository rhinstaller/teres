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
import StringIO


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


def _format_msg(record):
    """
    Method that takes care of formatting a message.
    """
    res = teres.result_to_name(record.result)
    spaces = 10 - 3 - len(res)

    head = ":: [   " + res + " " * spaces + "] :: "

    return head + record.msg


def _path_to_name(path):
    """
    Simple function to get nice log name.
    """
    return os.path.basename(path).replace(' ', '_')


class LoggingHandler(teres.Handler):
    """
    A handler class which writes the test results to a file.
    """

    def __init__(self,
                 name,
                 handlers,
                 result_level=teres.INFO,
                 process_logs=True,
                 dest="/tmp/"):
        super(LoggingHandler, self).__init__(result_level, process_logs)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(_result_to_level(self.result_level))

        if not isinstance(handlers, collections.Iterable):
            handlers = [handlers]

        for handler in handlers:
            self.logger.addHandler(handler)

        self.name = name
        self.dest = dest
        self.logdir = None
        if dest is not None:
            self.logdir = tempfile.mkdtemp(prefix='{}.'.format(self.name),
                                           dir=self.dest)
            self.logger.debug(
                "Create a directory {} to store log files.".format(
                    self.logdir))

    def _emit_log(self, record):
        self.logger.log(_result_to_level(record.result), _format_msg(record))

    def _emit_file(self, record):
        if self.logdir is None:
            self.logger.debug("Not copying, logdir is set to None.")
            return

        # Process files specified by path.
        if isinstance(record.logfile, str):
            if record.logname is None:
                record.logname = _path_to_name(record.logfile)

            msg = 'Sending file "{}" as "{}".'.format(record.logfile,
                                                      record.logname)

            record.logfile = open(record.logfile, 'rb')

        elif isinstance(record.logfile, file):
            # Take care of temporary files (created by mkstemp).
            if record.logfile.name == "<fdopen>" and record.logname is None:
                self.logger.warning(
                    "Logname parameter is mandatory if logfile is file like object.")
                return
            # Regular files without name provided.
            elif record.logname is None:
                record.logname = record.logfile.name

            msg = 'Sending file "{}".'.format(record.logname)

        elif isinstance(record.logfile, StringIO.StringIO):
            # Take care of StringIO file like objects.
            if record.logname is None:
                self.logger.warning(
                    "Logname parameter is mandatory if logfile is file like object.")
                return
            msg = 'Sending file "{}".'.format(record.logname)

        else:
            self.logger.error("Unable to handle this file type.")

        self.logger.debug("LoggingHandler: calling _emit_file: %s as %s",
                          record.logfile, record.logname)

        # Copy the contents.
        position = record.logfile.tell()
        if position:
            record.logfile.seek(0)
            with open("{}/{}".format(self.logdir, record.logname), "w") as fd:
                shutil.copyfileobj(record.logfile, fd)
            record.logfile.seek(position)
        else:
            with open("{}/{}".format(self.logdir, record.logname), "w") as fd:
                shutil.copyfileobj(record.logfile, fd)

        self._emit_log(teres.ReportRecord(teres.FILE, msg))

    def close(self):
        """
        LoggingHandler does not need cleanup but it's called by Reporter in
        destructor.
        """
        pass
