from __future__ import print_function
import unittest

import sys, os
my_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, my_path + '/../')

import requests
import teres
import teres.bkr_handlers
import tempfile

ENV = not bool(os.environ.get("BEAKER_RECIPE_ID") and os.environ.get("BEAKER_LAB_CONTROLLER_URL"))

@unittest.skipIf(ENV, "Beaker environment variables are not set.")
class BkrEnv(unittest.TestCase):
    def setUp(self):
        self.reporter = teres.Reporter()

        self.handler = teres.bkr_handlers.ThinBkrHandler()
        self.assertIsNotNone(self.handler.recipe_id)
        self.assertIsNotNone(self.handler.lab_controller_url)

        self.reporter.add_handler(self.handler)

    def assertEqualLong(self, test, reference):

        t = test.splitlines()
        r = reference.splitlines()

        try:
            for i in range(max(len(t), len(r))):
                self.assertEqual(t[i], r[i])
        except IndexError:
            self.fail("Test string and reference string are of different length.")


class BkrTest(BkrEnv):
    def test_simple_messages(self):
        """
        Test posting of simple messages to beaker.
        """
        self.reporter.log_error("error msg")
        self.reporter.log_fail("fail msg")
        self.reporter.log_pass("pass msg")
        self.reporter.log_info("info msg")
        self.reporter.log_debug("debug msg")

        self.reporter.test_end()

        # Check the results.
        ref = """:: [   ERROR  ] :: error msg
:: [   FAIL   ] :: fail msg
:: [   PASS   ] :: pass msg
:: [   INFO   ] :: info msg
"""

        url = self.handler._get_task_url() + "logs/testout.log"
        content = requests.get(url).content

        self.assertEqualLong(ref, content)

    def test_file_names(self):
        """
        Test file naming of logs sent to beaker.
        """
        self.reporter.send_file('/proc/cmdline')
        self.reporter.send_file('/proc/cpuinfo', logname="custom_file_name")

        f = open("/tmp/foo bar", "w+")
        f.close()
        self.reporter.send_file('/tmp/foo bar')

        tmp = tempfile.TemporaryFile()
        tmp.write("I'm a temporary file.")
        self.reporter.send_file(tmp)
        self.reporter.send_file(tmp, logname="tmp_file")

        self.reporter.test_end()

        # Check the results.
        ref = """:: [   FILE   ] :: Sending file "/proc/cmdline" as "cmdline".
:: [   FILE   ] :: Sending file "/proc/cpuinfo" as "custom_file_name".
:: [   FILE   ] :: Sending file "/tmp/foo bar" as "foo_bar".
:: [   FILE   ] :: Sending file "tmp_file".
"""

        url = self.handler._get_task_url() + "logs/testout.log"
        content = requests.get(url).content

        self.assertEqualLong(ref, content)

if __name__ == '__main__':
    unittest.main()
