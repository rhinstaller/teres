from __future__ import print_function
import unittest

import teres
import teres.handlers
import logging
import os.path
import shutil
import io
import tempfile


class LoggingHandlerSetUp(unittest.TestCase):
    def setUp(self):
        self.reporter = teres.Reporter.get_reporter()

        self.logger = logging.getLogger("test.logger")
        self.loghan_path = "/tmp/logging_handler_test.log"
        self.loghan = logging.FileHandler(self.loghan_path,
                                          mode='w')
        self.loghan.setLevel(logging.DEBUG)
        self.logger.addHandler(self.loghan)

        self.handler = teres.handlers.LoggingHandler("logginghandler.test",
                                                     self.logger,
                                                     dest="/tmp/")

        self.reporter.add_handler(self.handler)

    def tearDown(self):
        teres.Reporter.drop_reporter()
#        shutil.rmtree(self.handler.logdir)


class LoggingHandlerTest(LoggingHandlerSetUp):
    def test_log_ordinary_file_simple(self):
        test = "test_log_ordinary_file"
        text = "This is my log file."

        src_file = "/tmp/test log file"
        fd = open(src_file, "w")
        fd.write(text)
        fd.close()

        self.reporter.send_file(src_file)

        # Check the result.
        self.assertTrue(os.path.isdir(self.handler.logdir))

        tgt = open("{}/{}".format(self.handler.logdir, "test_log_file"))
        content = tgt.read()
        tgt.close()

        self.assertEqual(content, text)
        os.remove(src_file)

    def test_log_stringio_file(self):
        test = "test_log_stringio_file"
        text = u"This is my stringio file."

        src_file = io.StringIO(text)

        self.reporter.send_file(src_file, logname=test)

        # Check the result.
        self.assertTrue(os.path.isdir(self.handler.logdir))

        tgt = open("{}/{}".format(self.handler.logdir, test))
        content = tgt.read()
        tgt.close()

        self.assertEqual(content, text)

    def test_log_temp_file(self):
        test = "test_log_temp_file"
        text = "This is my temporary file."

        src_file = tempfile.TemporaryFile()
        src_file.write(text)
        self.reporter.send_file(src_file, logname=test)
        src_file.close()

        # Check the result.
        self.assertTrue(os.path.isdir(self.handler.logdir))

        tgt = open("{}/{}".format(self.handler.logdir, test))
        content = tgt.read()
        tgt.close()

        self.assertEqual(content, text)
