from __future__ import print_function
import unittest

import sys, os
my_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, my_path + '/../')

import requests
import teres
import teres.bkr_handlers

ENV = not bool(os.environ.get("BEAKER_RECIPE_ID") and os.environ.get("BEAKER_LAB_CONTROLLER_URL"))

@unittest.skipIf(ENV, "Beaker environment variables are not set.")
class BkrEnv(unittest.TestCase):
    def setUp(self):
        self.reporter = teres.Reporter()

        self.handler = teres.bkr_handlers.ThinBkrHandler()
        self.assertIsNotNone(self.handler.recipe_id)
        self.assertIsNotNone(self.handler.lab_controller_url)

        self.reporter.add_handler(self.handler)


class BkrTest(BkrEnv):
    def test_messages(self):
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
        log = requests.get(url)

        self.assertEqual(ref,log.content)

if __name__ == '__main__':
    unittest.main()
