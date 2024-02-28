"""Test the CLI"""
import unittest
from oxn.argparser import parser
from oxn.argparser import parse_oxn_args
import unittest.mock as mock


class CommandLineTests(unittest.TestCase):
    experiment_spec_mock = "some_experiment_spec.yaml"

    @mock.patch("argparse.ArgumentParser._print_message", mock.MagicMock)
    def test_it_throws_nonexisting_spec(self):
        test_args = [self.experiment_spec_mock]
        with self.assertRaises(SystemExit):
            parser.parse_args(args=test_args)

    @mock.patch("os.path.exists")
    def test_it_accepts_spec_file(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock]
        parsed = parser.parse_args(args=test_args)
        self.assertTrue(parsed.spec)

    @mock.patch("os.path.exists")
    def test_it_accepts_report_paths(self, mock_exists):
        mock_exists.return_value = True
        test_args = [
            self.experiment_spec_mock,
            "--report",
            "some_experiment_report.yml",
        ]
        parsed = parser.parse_args(args=test_args)
        self.assertTrue(parsed)
        self.assertTrue(parsed.report == "some_experiment_report.yml")

    @mock.patch("os.path.exists")
    def test_it_accepts_timeout(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock, "--timeout", "120s"]
        parsed = parser.parse_args(test_args)
        self.assertTrue(parsed)
        self.assertTrue(parsed.timeout == "120s")

    @mock.patch("os.path.exists")
    def test_it_accepts_times(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock, "--times", "100"]
        parsed = parser.parse_args(test_args)
        self.assertTrue(parsed)
        self.assertTrue(parsed.times == 100)

    @mock.patch("os.path.exists")
    def test_it_accepts_loglevel(self, mock_exist):
        mock_exist.return_value = True
        test_args = [self.experiment_spec_mock, "--loglevel", "debug"]
        parsed = parser.parse_args(test_args)
        self.assertTrue(parsed)
        self.assertTrue(parsed.log_level == "debug")

    @mock.patch("os.path.exists")
    @mock.patch("argparse.ArgumentParser._print_message", mock.MagicMock)
    def test_it_errors_on_invalid_loglevel(self, mock_exist):
        mock_exist.return_value = True
        test_args = [self.experiment_spec_mock, "--loglevel", "invalid_loglevel"]
        with self.assertRaises(SystemExit):
            parser.parse_args(test_args)

    @mock.patch("os.path.exists")
    def test_it_accepts_extend_argument(self, mock_exists):
        mock_exists.return_value = True
        test_args = [
            self.experiment_spec_mock,
            "--extend",
            # dummy file that exists
            self.experiment_spec_mock,
        ]
        parsed = parser.parse_args(test_args)
        self.assertTrue(parsed.extend == self.experiment_spec_mock)

    @mock.patch("os.path.exists")
    def test_it_accepts_logfile(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock, "--logfile", "some_log_file.txt"]
        parsed = parser.parse_args(test_args)
        self.assertTrue(parsed.log_file == "some_log_file.txt")

    @mock.patch("os.path.exists")
    def test_it_accepts_randomize(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock, "--randomize"]
        parsed = parser.parse_args(test_args)
        self.assertTrue(parsed.randomize)

    @mock.patch("os.path.exists")
    @mock.patch("argparse.ArgumentParser._print_message", mock.MagicMock)
    def test_it_throws_on_accounting_without_report(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock, "--accounting"]
        with self.assertRaises(SystemExit):
            parse_oxn_args(args=test_args)

    @mock.patch("os.path.exists")
    def test_it_accepts_accounting_with_report(self, mock_exists):
        mock_exists.return_value = True
        test_args = [
            self.experiment_spec_mock,
            "--accounting",
            "--report",
            "some_example_report.yaml",
        ]
        args = parse_oxn_args(args=test_args)
        self.assertTrue(args.accounting)
        self.assertTrue(args.report)

    @mock.patch("os.path.exists")
    def test_it_has_default_timeout(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock]
        parsed = parser.parse_args(test_args)
        self.assertTrue(parsed.timeout == "1m")

    @mock.patch("os.path.exists")
    def test_it_has_default_accounting(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock]
        parsed = parser.parse_args(test_args)
        self.assertFalse(parsed.accounting)

    @mock.patch("os.path.exists")
    def test_it_has_default_randomize(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock]
        parsed = parser.parse_args(test_args)
        self.assertFalse(parsed.randomize)

    @mock.patch("os.path.exists")
    def test_it_has_default_times(self, mock_exists):
        mock_exists.return_value = True
        test_args = [self.experiment_spec_mock]
        parsed = parser.parse_args(test_args)
        self.assertTrue(parsed.times == 1)
