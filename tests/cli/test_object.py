import unittest

from backup_tool.exception import CLIException
from backup_tool.cli.object import parse_args
from backup_tool.cli.object import DEFAULT_CONFIG_PATH


class TestCLIObject(unittest.TestCase):
    def test_no_module(self):
        with self.assertRaises(CLIException) as error:
            args = parse_args([])
        self.assertEqual("Missing args: No module provided", str(error.exception))

    def test_common_args_defaults(self):
        args = parse_args(["object", "list", "foo", "bar"])
        self.assertEqual(args['config_file'], DEFAULT_CONFIG_PATH)
        self.assertEqual(args['config_stage'], "DEFAULT")

    def test_common_args_config_file(self):
        args = parse_args(["-c", "foo", "object", "list", "foo3", "bar"])
        self.assertEqual(args['config_file'], "foo")

        args = parse_args(["--config-file", "foo2", "object", "list", "foo3", "bar"])
        self.assertEqual(args['config_file'], "foo2")

    def test_common_args_config_stage(self):
        args = parse_args(["-s", "foo", "object", "list", "foo3", "bar"])
        self.assertEqual(args['config_stage'], "foo")

        args = parse_args(["--config-stage", "foo2", "object", "list", "foo3", "bar"])
        self.assertEqual(args['config_stage'], "foo2")

    def test_object(self):
        with self.assertRaises(CLIException) as error:
            args = parse_args(["object"])
        self.assertEqual("Missing args: No command provided", str(error.exception))

    def test_object_list(self):
        with self.assertRaises(CLIException) as error:
            args = parse_args(["object", "list"])
        self.assertEqual("the following arguments are required: namespace_name, bucket_name",
                         str(error.exception))

        args = parse_args(["object", "list", "foo", "bar"])
        self.assertEqual(args, {
            "module" : "object",
            "command" : "list",
            "namespace_name" : "foo",
            "bucket_name" : "bar",
            "config_stage" : "DEFAULT",
            "config_file" : DEFAULT_CONFIG_PATH,
        })

    def test_object_put(self):
        with self.assertRaises(CLIException) as error:
            args = parse_args(["object", "put"])
        self.assertEqual("the following arguments are required: namespace_name, bucket_name, object_name, file_name",
                         str(error.exception))

        args = parse_args(["object", "put", "foo", "bar", "foo2", "bar2"])
        self.assertEqual(args, {
            "module" : "object",
            "command" : "put",
            "namespace_name" : "foo",
            "bucket_name" : "bar",
            "object_name" : "foo2",
            "file_name" : "bar2",
            "config_stage" : "DEFAULT",
            "config_file" : DEFAULT_CONFIG_PATH,
        })

