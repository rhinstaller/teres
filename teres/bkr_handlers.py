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
Beaker handlers for the teres package.
"""

import os
import os.path
import tempfile
import requests
import libxml2
import logging
import teres
import threading
import time
import Queue
import StringIO


# Flags defintion
class Flag(object):
    """
    Class for defining flags used for modification of ThinBkrHandler behaviour.
    """

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "{}".format(self.name)

    def __repr__(self):
        return "{} {} object at {}>".format(
            str(type(self))[:-1], self.name, hex(id(self)))

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.name == other.name


TASK_LOG_FILE = Flag('TASK_LOG_FILE')  # boolean
SUBTASK_RESULT = Flag('SUBTASK_RESULT')  # optional parameter: path
SCORE = Flag('SCORE')  # mandatory parameter: score
SUBTASK_LOG_FILE = Flag('SUBTASK_LOG_FILE')  # optional parameter: result url
DEFAULT_LOG_DEST = Flag('DEFAULT_LOG_DEST')  # boolean

# Define record types since we need to propagate information about the type from
# the parent class.
_LOG = object()
_FILE = object()

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def _result_to_bkr(result):
    """
    This function translates teres results to beaker results.
    """
    mapping = {
        teres.FILE: "None",
        teres.ERROR: "Warn",
        teres.FAIL: "Fail",
        teres.PASS: "Pass",
        teres.INFO: "None",
        teres.DEBUG: "None",
        teres.NONE: "None",
    }

    return mapping[result]


def _format_msg(record):
    """
    Method that takes care of formatting a message.
    """
    res = teres.result_to_name(record.result)
    spaces = 10 - 3 - len(res)

    head = ":: [   " + res + " " * spaces + "] :: "

    return head + record.msg + "\n"


def _path_to_name(path):
    """
    Simple function to get nice log name.
    """
    return os.path.basename(path).replace(' ', '_')


class ThinBkrHandlerError(teres.HandlerError):
    """
    Exception for beaker handler module.
    """
    pass


class ThinBkrHandler(teres.Handler):
    """
    Simple handler for reporting results to beaker within one task. I should be
    capable only of reporting results such as PASS/FAIL/ERROR and upload log
    files. Both recipe_id and lab_controller_url are mandatory.
    """

    def __init__(self,
                 result_level=teres.INFO,
                 process_logs=True,
                 task_log_name="testout.log",
                 task_log_dir="/tmp/",
                 recipe_id=None,
                 lab_controller_url=None,
                 disable_subtasks=False,
                 flush_delay=15,
                 report_overall=None):
        super(ThinBkrHandler, self).__init__(result_level, process_logs)

        # This is a thread safe queue to pass logs and files to thread that
        # takes care of sending them to beaker.
        self.record_queue = Queue.Queue()

        # Read beaker environment variables to be able to communicate with lab
        # controller.
        self.recipe_id = recipe_id or os.environ.get("BEAKER_RECIPE_ID")
        self.lab_controller_url = lab_controller_url or os.environ.get(
            "BEAKER_LAB_CONTROLLER_URL")

        if self.recipe_id is None or self.lab_controller_url is None:
            raise ThinBkrHandlerError(
                "Both recipe_id and lab_controller_url are mandatory as parameters or environment variables (see beaker API).")

        self.default_log_dest = self._get_task_url()
        self.last_result_url = self.default_log_dest
        self.disable_subtasks = disable_subtasks

        # Prepare default test log.
        self.task_log_name = task_log_name
        self.task_log_dir = task_log_dir

        task_log_prefix = task_log_name + "."
        self.task_log = tempfile.TemporaryFile(prefix=task_log_prefix,
                                               dir=self.task_log_dir)

        # Keep track whether the thread is already finished. Prepare and run the
        # thread loop.
        self.finished = False
        self.flush_delay = flush_delay
        self.first_flush = True
        self.async_thread = threading.Thread(target=self._thread_loop)
        self.async_thread.daemon = True
        self.async_thread.start()

        # Track overall result.
        self.report_overall = report_overall
        self.overall_result = teres.NONE

    def _track_result(self, result):
        """
        Method used to update the overall result.
        """
        if result in (teres.FAIL, teres.PASS, teres.ERROR):
            self.overall_result = max(self.overall_result, result)

    def _get_recipe(self):
        """
        Get beaker recipe xml.
        """
        url = self.lab_controller_url + "/recipes/" + self.recipe_id + "/"

        return requests.get(url)

    def _get_running_task_id(self):
        """
        Get task id of running task.
        """
        recipe = self._get_recipe()
        xml = libxml2.parseDoc(recipe.content)
        try:
            current_taskid = xml.xpathEval(
                '/job/recipeSet/recipe/task[@status="Running"]/@id')[0].content
        except IndexError:
            raise ThinBkrHandlerError("Could not get running task id.")

        return current_taskid

    def _get_task_url(self):
        """Get current task url"""
        return self.lab_controller_url + "/recipes/" + self.recipe_id + "/tasks/" + self._get_running_task_id(
        ) + "/"

    def _generate_url(self, record):
        """
        Method to generate beaker url.
        """

        # Make following conditions more readable by creating following
        # variables.
        send_log = record.result == teres.FILE
        has_logfile = record.logfile is not None
        to_task = record.flags.get(TASK_LOG_FILE, False)
        to_subtask = record.flags.get(SUBTASK_LOG_FILE, False)
        subtask_result = record.flags.get(SUBTASK_RESULT, False)

        # Generate url for a task log.
        if send_log and has_logfile and to_task:
            return self._get_task_url() + "logs/" + record.logname + "/"

        # Generate url for log file to default destination.
        if send_log and has_logfile and not (to_task or to_subtask):
            return self.default_log_dest + "logs/" + record.logname + "/"

        # Generate url for a task result log.
        if send_log and has_logfile and to_subtask:

            if isinstance(to_subtask, str):
                return record.flags[
                    SUBTASK_LOG_FILE] + "logs/" + record.logname + "/"
            else:
                return self.last_result_url + "logs/" + record.logname + "/"

        # Generate url for subtask result.
        if subtask_result:
            return self._get_task_url() + "results/"

    def _emit_log(self, record):
        """
        Pass log records to the record_queue.
        """
        logger.debug("ThinBkrHandler: calling _emit_log with record %s",
                     record)
        self._track_result(record.result)
        self.record_queue.put((_LOG, record))

    def _thread_emit_log(self, record):
        """
        Send log record to beaker.
        """
        # Without any flags specified just write the message into the log file.
        self.task_log.write(_format_msg(record))
        logger.debug("ThinBkrHandler: calling _thread_emit_log with record %s",
                     record)

        subtask_result = record.flags.get(SUBTASK_RESULT, False)
        if subtask_result and not self.disable_subtasks:
            url = self._generate_url(record)

            data = {
                "result": _result_to_bkr(record.result),
                "message": record.msg,
            }

            if isinstance(subtask_result, str):
                data["path"] = subtask_result

            if record.flags.get(SCORE, False):
                data["score"] = record.flags[SCORE]

            req = requests.post(url, data)

            if req.status_code != 201:
                logger.warning("Result reporting failed with code: %s",
                               req.status_code)

            self.last_result_url = req.headers["Location"] + "/"

            if record.flags.get(DEFAULT_LOG_DEST, False):
                self.default_log_dest = self.last_result_url

        if self.first_flush:
            self.first_flush = False
            self._thread_flush()

    def _emit_file(self, record):
        """
        Pass file records to the record_queue.
        """
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
                logger.warning(
                    "Logname parameter is mandatory if logfile is file like object.")
                return
            # Regular files without name provided.
            elif record.logname is None:
                record.logname = record.logfile.name

            msg = 'Sending file "{}".'.format(record.logname)

        elif isinstance(record.logfile, StringIO.StringIO):
            # Take care of StringIO file like objects.
            if record.logname is None:
                logger.warning(
                    "Logname parameter is mandatory if logfile is file like object.")
                return
            msg = 'Sending file "{}".'.format(record.logname)

        else:
            logger.error("Unable to handle this file type.")

        logger.debug("ThinBkrHandler: calling _emit_file: %s as %s",
                     record.logfile, record.logname)

        self.record_queue.put((_FILE, record))
        self._emit_log(teres.ReportRecord(teres.FILE, msg))

    def _thread_emit_file(self, record):
        """
        Send file record to beaker.
        """
        url = self._generate_url(record)

        position = record.logfile.tell()
        record.logfile.seek(0)
        payload = record.logfile.read()
        record.logfile.seek(position)

        logger.debug("ThinBkrHandler: calling _thread_emit_file with: %s",
                     record.logname)

        req = requests.put(url, data=payload)
        if req.status_code != 204:
            logger.warning("Uploading failed with code %s", req.status_code)
            logger.warning("Destination URL: %s", url)

    def reset_log_dest(self):
        """
        Reset default log destination to task result instead of particular
        subtask result.
        """
        self.default_log_dest = self._get_task_url()

    def _thread_flush(self):
        """
        Send current state of the task log file to beaker whenever this is
        called. This is meant to enable continuous updating of the task log.
        """
        record = teres.ReportRecord(teres.FILE,
                                    None,
                                    logfile=self.task_log,
                                    logname=self.task_log_name)

        self._thread_emit_file(record)

    def close(self):
        """
        Set handler state to finished. Join the thread for asynchronous
        communication with beaker and finally close task log.
        """
        msg = "Test finished with the result: {}".format(teres.result_to_name(
            self.overall_result))
        self._emit_log(teres.ReportRecord(self.overall_result, msg))

        if self.report_overall is not None:
            self._emit_log(teres.ReportRecord(self.overall_result,
                                              self.report_overall,
                                              flags={SUBTASK_RESULT: True}))

        self.finished = True

        self.async_thread.join()
        self.task_log.close()

    def _thread_loop(self):
        """
        This is a thread loop for sending records to beaker asynchronously. In
        this way the program using this handler isn't blocked by the
        communication. Although it has to wait for the join when self.close() is
        called.
        """
        logger.info("ThinBkrHandler: start _thread_loop")
        synced = True
        last_update = time.time()

        while not (self.finished and self.record_queue.empty()):
            try:
                record_type, record = self.record_queue.get(timeout=0.1)

                if record_type == _LOG:
                    self._thread_emit_log(record)
                    synced = False
                elif record_type == _FILE:
                    self._thread_emit_file(record)

            except Queue.Empty:
                pass

            if not synced and (time.time() - last_update > self.flush_delay):
                self._thread_flush()
                synced = True
                last_update = time.time()

        # Last flush after close() was called.
        if not synced:
            self._thread_flush()

        logger.info("ThinBkrHandler: exitting _thread_loop")
