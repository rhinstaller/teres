from __future__ import print_function
import unittest
from unittest.mock import patch

import sys
import time
import tempfile
import shutil

import teres

DEBUG = True


def debug_var(obj, fn_name, name, value):
    if not DEBUG:
        return
    sys.stderr.write(
        '%s.%s(): %s=%r\n'
        % (
            obj.__class__.__name__,
            fn_name,
            name,
            value,
        )
    )


def debug_msg(obj, fn_name, msg):
    if not DEBUG:
        return
    sys.stderr.write(
        '%s.%s(): %s\n'
        % (
            obj.__class__.__name__,
            fn_name,
            msg,
        )
    )


class AutoText:
    """
    Automatic text generator (poor man's Lorem Ipsum generator).

    The text is optimized so that it's easy to glean from debug log
    which chunk is being uploaded.
    """

    def __init__(self, name):
        self.header = [
            "--- BEGIN %s ---" % name,
            "",
        ]
        self.nl = [""]
        self.par0 = [
            " 0. _ ___ __ _ _____ ___ ___ _ __ ___ ___ ___ ___ _ _ __",
            "",
        ]
        self.par1 = [
            " 1. a aaa aa a aaaaa aaa aaa a aa aaa aaa aaa aaa a a aa",
            "    a aaa aa a aaaaa aaa aaa a aa aaa aaa aaa aaa a a aa",
            "",
        ]
        self.par2 = [
            " 2. b bbb bb b bbbbb bbb bbb b bb bbb bbb bbb bbb b b bb",
            "    b bbb bb b bbbbb bbb bbb b bb bbb bbb bbb bbb b b bb",
            "    b bbb bb b bbbbb bbb bbb b bb bbb bbb bbb bbb b b bb",
            "",
        ]
        self.par3 = [
            " 3. c ccc cc c ccccc ccc ccc c cc ccc ccc ccc ccc c c cc",
            "    c ccc cc c ccccc ccc ccc c cc ccc ccc ccc ccc c c cc",
            "    c ccc cc c ccccc ccc ccc c cc ccc ccc ccc ccc c c cc",
            "    c ccc cc c ccccc ccc ccc c cc ccc ccc ccc ccc c c cc",
            "",
        ]
        self.par4 = [
            " 4. d ddd dd d ddddd ddd ddd d dd ddd ddd ddd ddd d d dd",
            "    d ddd dd d ddddd ddd ddd d dd ddd ddd ddd ddd d d dd",
            "    d ddd dd d ddddd ddd ddd d dd ddd ddd ddd ddd d d dd",
            "    d ddd dd d ddddd ddd ddd d dd ddd ddd ddd ddd d d dd",
            "    d ddd dd d ddddd ddd ddd d dd ddd ddd ddd ddd d d dd",
            "",
        ]
        self.footer = ["--- %s END ---" % name]


class LivingFile:
    """
    Scenario where a file is changing during its lifetime.

    The lifetime is tracked inside of the object in terms of "ticks".

    The object also tracks number of characters written and number
    of characters current file is expected to have.  Note that these
    are **not** bytes but characters in terms of elements of str().

    To use this class, sub-class it and implement _tick() method, which
    has to accept single argument of 'new_state' representing zero-based
    ordinal number of file state.  Use self._write and self._append to
    alter the file in order to correspond to the desired state new_state.

    To advance the scenario, run tick() method as many times as
    needed.  tick() is not called by any built-in methods, so before
    calling the first tick(), it's expected that the file does not
    exist yet.
    """

    name = '_unknown_'

    def __init__(self, root, max_state):
        self.root = root
        self.path = root + '/' + self.name
        self.max_state = max_state
        self.next_state = 0
        self.wrote_so_far = 0
        self.expected_size = 0

    def _append(self, lines=None, text=None):
        """
        Append lines and text.

        Same as self._write() but any data is appended to the end of the
        file.
        """
        self.__write(append=True, lines=lines, text=text)

    def _write(self, lines=None, text=None):
        """
        Write lines and text to self.path.

        Arguments *lines* and *text* specify string data to write.

        *lines* must be list of strings; each element will be appended
        the newline character before writing.  *lines* defaults to empty
        list, ie. no writes.

        *text* can be list of characters which will be left intact.
        *text* defaults to empty string, ie. a single write operation
        with no data.  (This will still clobber the file or create new
        one.)
        """
        self.__write(append=False, lines=lines, text=text)

    def __write(self, append=False, lines=None, text=None):
        text = text or ''
        lines = lines or []
        data = ''
        for ln in lines:
            data += (ln + '\n')
        data += text
        self.__count_and_write(
            path=self.path,
            mode='a' if append else 'w',
            data=data
        )

    def __count_and_write(self, path, mode, data):
        if mode == 'w':
            self.expected_size = 0
        debug_msg(self, '__count_and_write', '%s %d bytes' % (mode, len(data)))
        with open(self.path, mode) as fh:
            fh.write(data)
            self.wrote_so_far += len(data)
            self.expected_size += len(data)

    def _tick(self, new_state):
        """
        Alter file towards the state id *new_state*.

        Do this by calling self._write() or self._append().
        """
        raise NotImplementedError("LivingFile base class must be sub-classed, overriding _tick()")

    def make_autotext(self):
        """
        Create AutoText object for us.
        """
        return AutoText(self.__class__.__name__)

    def tick(self):
        """
        Update file once.
        """
        self._tick(self.next_state)
        self.next_state += 1


class EmptyFile(LivingFile):

    name = 'empty'

    def _tick(self, new_state):
        if new_state == 0:
            self._write(text='')


class StableFile(LivingFile):

    name = 'stable'

    def _tick(self, new_state):
        a = self.make_autotext()
        if new_state == 0:
            self._write(lines=a.header+a.par1+a.par2+a.par3+a.footer)


class GrowingFile(LivingFile):
    """
    A file that is growing, ie. only appending text on top of initial
    header.
    """

    name = 'growing'

    def _tick(self, new_state):
        a = self.make_autotext()
        if new_state == 0:
            self._write(lines=a.header)
        elif new_state == 1:
            self._append(lines=a.par1)
        elif new_state == 2:
            self._append(lines=a.par2)
        elif new_state == 3:
            self._append(lines=a.par3)
        elif new_state == 4:
            self._append(lines=a.footer)


class ChangingFile(LivingFile):
    """
    Middle section of the file is changing once per tick.
    """

    name = 'changing'

    def _tick(self, new_state):
        a = self.make_autotext()
        if new_state == 0:
            self._write(lines=a.header+a.par0+a.footer)
        elif new_state == 1:
            self._write(lines=a.header+a.par1+a.footer)
        elif new_state == 2:
            self._write(lines=a.header+a.par2+a.footer)
        elif new_state == 3:
            self._write(lines=a.header+a.par3+a.footer)


class ShrinkingFile(LivingFile):

    name = 'shrinking'

    def _tick(self, new_state):
        a = self.make_autotext()
        if new_state == 0:
            self._write(lines=a.header+a.par1+a.par2+a.par3+a.footer)
        elif new_state == 1:
            self._write(lines=a.header+a.par1+a.par2+a.footer)
        elif new_state == 2:
            self._write(lines=a.header+a.par1+a.footer)
        elif new_state == 3:
            self._write(lines=a.header+a.footer)


class ResultTracker:
    """
    Utility class to keep track of mocked SUT http_put() function
    and help collect data relevant for further test asserts.
    """

    def __init__(self, mock, file):
        """
        Create tracker of http_put Mock object *mock*, tracking
        calls that upload files represented by LivingFile *file*.
        """
        self.file = file
        self.mock = mock

    def debug_stats(self):
        """
        Describe what our http_put() and LivingFile have been up to.
        """
        def describe_call(C):
            url = C[0][0]
            payload = C[0][1]
            return (
                "call sending %d bytes to http:/..%s, preview: %r .. %r"
                % (
                    len(payload),
                    url[-20:],
                    payload[:20].decode(),
                    payload[-20:].decode(),
                )
            )
        debug_var(self, 'debug_stats', 'self.file.wrote_so_far', self.file.wrote_so_far)
        debug_var(self, 'debug_stats', 'self.file.expected_size', self.file.expected_size)
        debug_var(self, 'debug_stats', 'len(self.calls)', len(self.calls))
        for call in self.calls:
            debug_msg(self, 'debug_stats', ' .. ' + describe_call(call))

    @property
    def calls(self):
        """
        Return all calls from tracked object (Mock.call_args_list)
        where url contains name of tracked file.
        """
        return [c for c in self.mock.call_args_list
                if self.file.name in c[0][0]]

    @property
    def total_uploaded(self):
        """
        Return total of uploaded bytes of tracked file.
        """
        return sum([len(c[0][1]) for c in self.calls])


@patch('teres.bkr_handlers.http_put')
class MockedBkrTest(unittest.TestCase):

    @patch('teres.bkr_handlers.http_get')
    @patch('teres.bkr_handlers.ThinBkrHandler._get_running_task_id', return_value='1234')
    def make_reporter(self, mock_get, mock_grti):
        reporter = teres.Reporter()
        reporter.add_handler(teres.bkr_handlers.ThinBkrHandler(
            recipe_id='1234',
            lab_controller_url='http://localhost:5678',
        ))
        return reporter

    def setUp(self, *args, **kwargs):
        debug_var(self, 'setUp', 'args', args)
        debug_var(self, 'setUp', 'kwargs', kwargs)
        self.reporter = self.make_reporter()
        self.tmp = tempfile.mkdtemp()
        self.mock_http_put = teres.bkr_handlers.http_put

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _sleep_hack(self):
        """
        Test handler for LivingFile to send the file.

        We're using "stupid" sleep, but without it some tests behave weirdly:
        ThinBkrHandler is handling the POST requests in a separate thread, by
        pulling from a queue.  But the queue does not contain the data to POST,
        just the "order" to POST data from a given file handler.
        Therefore ThinBkrHandler.send_file will optimize by "disobeying" the
        order if there was no new data or sending just the new data if there
        is some.  (It will also keep track of the last posted byte and use
        Content-Range HTTP header to creata an appending POST.)

        This means that if a file is changing faster than the queue (in separate
        thread) is being processed, some states of the file might be ignored.

        For example, a file has 200 bytes, then shrinks to 100 bytes, then grows
        to 300 bytes.  If we call ThinBkrHandler.send_file after each of these
        changes, it's a matter of race condition what will be really POSTed.
        If the thread is scheduled (by OS) after the second file's change,
        ThinBkrHandler.send_file will only see the 100-byte file,  if it's
        later, ThinBkrHandler.send_file will only see the 300-byte file, etc.

        So time.sleep(0.2) seems to "fix" this; a small justification for now
        might be that it's probably more realistic for the calls to have some
        gap between them.
        """
        time.sleep(0.2)

    def prep_result(self, lf_cls, mock_put, reupload=False, states=5):
        """
        Run test scenario using LivingFile sub-class and return
        collected results in form of tuple of the ResultTracker
        (tracking the given LivingFile instance) and the LivingFile
        instance itself.
        """

        def send_file():
            self.reporter.send_file(file.path, file.name)

        def reupload_file():
            flags = {teres.bkr_handlers.REUPLOAD: True}
            self.reporter.send_file(file.path, file.name, flags=flags)

        file = lf_cls(self.tmp, states)
        res = ResultTracker(mock_put, file)

        # go through the whole changing/uploading scenario
        #
        while file.next_state <= states:
            file.tick()
            reupload_file() if reupload else send_file()
            self._sleep_hack()
        self.reporter.test_end()
        res.debug_stats()
        return res

    def test_growing_file(self, mock_put):
        res = self.prep_result(GrowingFile, mock_put)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 567)

    def test_empty_file(self, mock_put):
        res = self.prep_result(EmptyFile, mock_put)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 0)

    def test_shrinking_file(self, mock_put):
        res = self.prep_result(ShrinkingFile, mock_put)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 571)

    def test_stable_file(self, mock_put):
        res = self.prep_result(StableFile, mock_put)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 565)

    def test_changing_file(self, mock_put):
        res = self.prep_result(ChangingFile, mock_put)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 282)

    def test_growing_file_reupload(self, mock_put):
        res = self.prep_result(GrowingFile, mock_put, reupload=True)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 2160)

    def test_empty_file_reupload(self, mock_put):
        res = self.prep_result(EmptyFile, mock_put, reupload=True)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 0)

    def test_shrinking_file_reupload(self, mock_put):
        res = self.prep_result(ShrinkingFile, mock_put, reupload=True)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 1248)

    def test_stable_file_reupload(self, mock_put):
        res = self.prep_result(StableFile, mock_put, reupload=True)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 3390)

    def test_changing_file_reupload(self, mock_put):
        res = self.prep_result(ChangingFile, mock_put, reupload=True)
        self.assertGreaterEqual(len(res.calls), 1)
        self.assertEqual(res.total_uploaded, 1350)


if __name__ == '__main__':
    unittest.main()
