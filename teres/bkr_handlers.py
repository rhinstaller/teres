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
import xml.etree.ElementTree
import logging
import teres
import threading
import time
import io
import datetime
import functools
import socket
from urllib.parse import urlencode
from urllib.request import urlopen, build_opener, Request, HTTPHandler
from queue import Queue
from queue import Empty as QueueEmpty

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

    def __hash__(self):
        return hash((self.name,))


TASK_LOG_FILE = Flag('TASK_LOG_FILE')  # boolean
SUBTASK_RESULT = Flag('SUBTASK_RESULT')  # optional parameter: path
SCORE = Flag('SCORE')  # mandatory parameter: score
SUBTASK_LOG_FILE = Flag('SUBTASK_LOG_FILE')  # optional parameter: result url
DEFAULT_LOG_DEST = Flag('DEFAULT_LOG_DEST')  # boolean
QUIET_FILE = Flag('QUIET_FILE')  # boolean
REUPLOAD = Flag('REUPLOAD')  # boolean

# Define record types since we need to propagate information about the type from
# the parent class.
_LOG = object()
_FILE = object()

# Constants
HTTP_TIMEOUT = 30
HTTP_RETRIES = 3

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def decoded(func):
    functools.wraps(func)
    def wrapper(*args, **kwargs):
        return teres.make_text(func(*args, **kwargs))
    return wrapper


@decoded
def http_get(url):
    """
    Function to simplify interaction with urllib.
    """
    for i in range(HTTP_RETRIES):
        try:
            urllib_obj = urlopen(url, timeout=HTTP_TIMEOUT)
            break
        except socket.timeout:
            logger.error(
                "(%d/%d) http_get hit timeout on URL: %s",
                i, HTTP_RETRIES, url
            )
    if urllib_obj.getcode() != 200:
        logger.warning("Couldn't get URL: %s", url)
    else:
        return urllib_obj.read()


@decoded
def http_post(url, data):
    """
    Function to simplify interaction with urllib.
    """
    payload = urlencode(data)
    for i in range(HTTP_RETRIES):
        try:
            urllib_obj = urlopen(url, teres.make_bytes(payload), timeout=HTTP_TIMEOUT)
            break
        except socket.timeout:
            logger.error(
                "(%d/%d) http_post hit timeout on URL: %s",
                i, HTTP_RETRIES, url
            )
    if urllib_obj.getcode() != 201:
        logger.warning("Result reporting to %s failed with code: %s", url, urllib_obj.getcode())
    else:
        return urllib_obj


@decoded
def http_put(url, payload, **headers):
    """
    Function to simplify interaction with urllib.
    """
    logger.debug('http_put(): url=%r' % url)
    logger.debug('http_put(): len(payload)=%r, payload[0:20]=%r)'
                 % (len(payload), payload[0:20]))
    logger.debug('http_put(): headers=%r' % headers)
    opener = build_opener(HTTPHandler)
    req = Request(url, data=teres.make_bytes(payload))
    req.add_header('Content-Type', 'text/plain')
    for header, value in headers.items():
        req.add_header(header, value)
    req.get_method = lambda: 'PUT'
    for i in range(HTTP_RETRIES):
        try:
            url = opener.open(req, timeout=HTTP_TIMEOUT)
            break
        except socket.timeout:
            logger.error(
                "(%d/%d) http_put hit timeout on URL: %s",
                i, HTTP_RETRIES, url
            )

    if url.getcode() != 204:
        logger.warning("Uploading to %s failed with code %s", url, req.status_code)
    else:
        return url


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

    timestr = datetime.datetime.fromtimestamp(record.timestamp).strftime("%Y-%m-%d %H:%M:%S.%f ")
    head = ":: [   " + res + " " * spaces + "] :: "

    return "{}{}{}\n".format(timestr, head, record.msg)


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


class _IncrementalUploader:
    """
    Uploader utility object that will keep track of previous uploads and
    try to detect when a file has grown since last upload and upload just
    the new bytes.

    Note that this detection is very naiive.  For files that might change
    in any other way than appending new bytes, you probably only want to
    make sure to only use upload_whole().

    The detection also does not respect file path; file identity is tracked
    only in terms of URL.  (That is, uploading file to different URL's will
    upload twice, but uploading different files to same URL will probably
    break the detection.)
    """

    def __init__(self):
        self._next_chunk_pos = {}

    def upload_chunk(self, handle, url):
        """
        Upload increment (added bytes) from file-like *handle* a to URL *url*.

        Based on previous uploads (either invoked by this method or upload_whole()),
        read only new bytes and "remember" the upload.
        """
        if url not in self._next_chunk_pos:
            # new file (0 size is ok)
            self.upload_whole(handle, url)
            return
        range_from = self._next_chunk_pos[url]
        payload, range_from, range_to = self._tell_read_seek(handle, range_from)
        if not payload:
            logger.info("_IncrementalUploader: nothing new to upload: 0 bytes for %s" % url)
            return
        logger.info("_IncrementalUploader: uploading file chunk: %d bytes to %s" % (len(payload), url))
        headers = {'Content-Range': 'bytes %d-%d/*' % (range_from, range_to)}
        http_put(url, payload, **headers)
        self._next_chunk_pos[url] = range_to + 1

    def upload_whole(self, handle, url):
        """
        Upload all bytes from file-like *handle* to URL *url*.

        Keep record of uploaded bytes so that if file grows, subsequent calls
        to upload_chunk() will upload only the newly added bytes.
        """
        payload, range_from, range_to = self._tell_read_seek(handle)
        if url in self._next_chunk_pos:
            logger.info("_IncrementalUploader: re-uploading file: %d bytes to %s"
                        % (len(payload), url))
        else:
            logger.info("_IncrementalUploader: uploading new file: %d bytes to %s"
                        % (len(payload), url))
        http_put(url, payload)
        self._next_chunk_pos[url] = range_to + 1

    def _tell_read_seek(self, handle, range_from=0):
        """
        Read payload from file-like *handle* and return it including suggested
        chunk upload range.

        This method will seek inside the file but restore the handle cursor
        afterwards.

        Note that even though we restore the cursor,  this is not a thread-safe
        operation as the tell-read-seek is a non-atomic sequence and another
        thread reading from the same file in the meantime would likely get
        corrupted data.  Also if the file is a stream (pipe or a stream device)
        then the read itself is irreversibly altering external state.
        """
        cursor_backup = handle.tell()
        handle.seek(range_from)
        payload = handle.read()
        handle.seek(cursor_backup)
        range_to = range_from + len(payload) - 1
        return payload, range_from, range_to


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
        self.record_queue = Queue()

        # Uploader for _thread_emit_file() to keep track of
        # what was uploaded.
        self._uploader = _IncrementalUploader()

        # Read beaker environment variables to be able to communicate with lab
        # controller.
        self.recipe_id = recipe_id and str(recipe_id) or os.environ.get("BEAKER_RECIPE_ID")
        self.lab_controller_url = lab_controller_url or os.environ.get(
            "BEAKER_LAB_CONTROLLER_URL")

        if self.recipe_id is None or self.lab_controller_url is None:
            raise ThinBkrHandlerError(
                """Both recipe_id and lab_controller_url are mandatory as parameters or environment variables.
# export BEAKER_RECIPE_ID=<id>
# export BEAKER_LAB_CONTROLLER_URL=<lab controller url>""")

        self.default_log_dest = self._get_task_url()
        self.last_result_url = self.default_log_dest
        self.disable_subtasks = disable_subtasks

        # Prepare default test log.
        self.task_log_name = task_log_name
        self.task_log_dir = task_log_dir

        task_log_prefix = task_log_name + "."
        self.task_log = tempfile.TemporaryFile(
            prefix=task_log_prefix, dir=self.task_log_dir)

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

        return http_get(url)

    def _get_running_task_id(self):
        """
        Get task id of running task.
        """
        recipe = self._get_recipe()
        doc = xml.etree.ElementTree.fromstring(recipe)

        try:
            for task in doc.findall('./recipeSet/recipe//task'):
                if task.attrib['status'] in ("Running", "Waiting"):
                    return task.attrib['id']
        except IndexError:
            raise ThinBkrHandlerError(
                "Could not find any running/waiting task id.")

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
        self.task_log.write(teres.make_bytes(_format_msg(record)))
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

            req = http_post(url, data)

            self.last_result_url = req.getheader("Location") + "/"

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

        elif isinstance(record.logfile, io.StringIO):
            # Take care of StringIO file like objects.
            if record.logname is None:
                logger.warning(
                    "Logname parameter is mandatory if logfile is file like object."
                )
                return
            msg = 'Sending file "{}".'.format(record.logname)

        elif isinstance(record.logfile, teres.FILE_TYPES):
            # Take care of temporary files (created by mkstemp).
            if (record.logfile.name == "<fdopen>" or isinstance(
                    record.logfile.name, int)) and record.logname is None:
                logger.warning(
                    "Logname parameter is mandatory if logfile is file like object."
                )
                return
            # Regular files without name provided.
            elif record.logname is None:
                record.logname = record.logfile.name

            msg = 'Sending file "{}".'.format(record.logname)

        else:
            logger.error("Unable to handle this file type.")
            return

        logger.debug("ThinBkrHandler: calling _emit_file: %s as %s",
                     record.logfile, record.logname)

        self.record_queue.put((_FILE, record))
        if not record.flags.get(QUIET_FILE, False):
            self._emit_log(teres.ReportRecord(teres.FILE, msg))

    def _thread_emit_file(self, record):
        """
        Send file record to beaker.
        """
        url = self._generate_url(record)
        reuploading = record.flags.get(REUPLOAD, False)
        if reuploading:
            self._uploader.upload_whole(record.logfile, url)
        else:
            self._uploader.upload_chunk(record.logfile, url)

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
        record = teres.ReportRecord(
            teres.FILE,
            None,
            logfile=self.task_log,
            logname=self.task_log_name)

        self._thread_emit_file(record)

    def close(self):
        """
        Set handler state to finished. Join the thread for asynchronous
        communication with beaker and finally close task log.
        """
        msg = "Test finished with the result: {}".format(
            teres.result_to_name(self.overall_result))
        self._emit_log(teres.ReportRecord(self.overall_result, msg))

        if self.report_overall is not None:
            self._emit_log(
                teres.ReportRecord(
                    self.overall_result,
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

                logger.debug("THREAD(%s) start _thread_emit_*", threading.current_thread().ident)
                if record_type == _LOG:
                    logger.debug("THREAD(%s) _thread_emit_log", threading.current_thread().ident)
                    self._thread_emit_log(record)
                    synced = False
                elif record_type == _FILE:
                    logger.debug("THREAD(%s) _thread_emit_file", threading.current_thread().ident)
                    self._thread_emit_file(record)
                logger.debug("THREAD(%s) end _thread_emit_*", threading.current_thread().ident)

            except QueueEmpty:
                pass
            except Exception as e:
                logger.error("THREAD(%s) exception: %s", e)

            if not synced and not (0 < time.time() - last_update < self.flush_delay):
                self._thread_flush()
                synced = True
                last_update = time.time()

        # Last flush after close() was called.
        if not synced:
            self._thread_flush()

        logger.info("ThinBkrHandler: exitting _thread_loop")
