import unittest
from datetime import datetime

from oxn.utils import time_string_to_seconds, defer_cleanup
from oxn.utils import to_microseconds, to_milliseconds
from oxn.utils import utc_timestamp, humanize_utc_timestamp


class UtilsTest(unittest.TestCase):
    def test_zero_minutes(self):
        time_string = "0m"
        self.assertTrue(time_string_to_seconds(time_string=time_string) == 0)

    def test_ten_minutes(self):
        time_string = "10m"
        seconds = time_string_to_seconds(time_string)
        self.assertTrue(seconds == 10 * 60)

    def test_can_handle_mixed(self):
        time_string = "10m30s"
        seconds = time_string_to_seconds(time_string)
        self.assertTrue(seconds == (10 * 60) + 30)
        self.assertTrue(isinstance(seconds, float))

    def test_it_converts_to_microseconds(self):
        time_string = "1m"
        seconds = time_string_to_seconds(time_string)
        microseconds = to_microseconds(seconds)
        self.assertTrue(microseconds == seconds * 10**6)
        self.assertTrue(isinstance(microseconds, float))

    def test_it_converts_to_milliseconds(self):
        time_string = "1m"
        seconds = time_string_to_seconds(time_string)
        milliseconds = to_milliseconds(seconds)
        self.assertTrue(milliseconds == seconds * 10**3)
        self.assertTrue(isinstance(milliseconds, float))

    def test_it_humanizes_timestamps(self):
        now = utc_timestamp()
        humanized = humanize_utc_timestamp(now)
        self.assertTrue(isinstance(humanized, datetime))

    def test_it_sets_deferred_cleanup_attr(self):
        @defer_cleanup
        def func():
            pass

        self.assertTrue(func.defer_cleanup)
