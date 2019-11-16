import unittest

from backup_tool.exception import CLIException
from backup_tool.cli.client import parse_args
from backup_tool.cli.client import DEFAULT_SETTINGS_FILE


class TestCLIObject(unittest.TestCase):
    def test_no_module(self):
        with self.assertRaises(CLIException) as error:
            args = parse_args([])
        self.assertEqual("Missing args: No module provided", str(error.exception))

    def test_common_args_defaults(self):
        args = parse_args(["file", "list"])
        self.assertEqual(args.pop('settings_file'), DEFAULT_SETTINGS_FILE)
        self.assertEqual(args.pop('config_file'), None)
        self.assertEqual(args.pop('config_stage'), None)
        self.assertEqual(args.pop('database_file'), None)
        self.assertEqual(args.pop('log_file'), None)
        self.assertEqual(args.pop('crypto_key_file'), None)
        self.assertEqual(args.pop('relative_path'), None)
        self.assertEqual(args.pop('namespace'), None)
        self.assertEqual(args.pop('bucket_name'), None)

        args.pop('module')
        args.pop('command')
        self.assertEqual(len(args), 0)

    def test_common_args_settings_file(self):
        args = parse_args(["-s" "foo", "file", "list"])
        self.assertEqual(args['settings_file'], "foo")
        args = parse_args(["--settings-file", "foo", "file", "list"])
        self.assertEqual(args['settings_file'], "foo")

    def test_common_args_config_file(self):
        args = parse_args(["-c", "foobar", "file", "list"])
        self.assertEqual(args['config_file'], 'foobar')
        args = parse_args(["--config-file", "foobar", "file", "list"])
        self.assertEqual(args['config_file'], 'foobar')

        args = parse_args(["-cs", "foobar2", "file", "list"])
        self.assertEqual(args['config_stage'], 'foobar2')
        args = parse_args(["--config-stage", "foobar2", "file", "list"])
        self.assertEqual(args['config_stage'], 'foobar2')

    def test_common_args_database_log(self):
        args = parse_args(["-d", "data", "file", "list"])
        self.assertEqual(args['database_file'], 'data')
        args = parse_args(["--database-file", "data", "file", "list"])
        self.assertEqual(args['database_file'], 'data')

        args = parse_args(["-l", "loggy", "file", "list"])
        self.assertEqual(args['log_file'], 'loggy')
        args = parse_args(["--log-file", "loggy", "file", "list"])
        self.assertEqual(args['log_file'], 'loggy')

    def test_common_args_crypto_relative(self):
        args = parse_args(["-k", "key", "file", "list"])
        self.assertEqual(args['crypto_key_file'], "key")
        args = parse_args(["--crypto-key-file", "key", "file", "list"])
        self.assertEqual(args['crypto_key_file'], "key")

        args = parse_args(["-r", "path", "file", "list"])
        self.assertEqual(args["relative_path"], "path")
        args = parse_args(["--relative-path", "path", "file", "list"])
        self.assertEqual(args["relative_path"], "path")

    def test_common_args_namespace_bucket(self):
        args = parse_args(["-n", "name", "file", "list"])
        self.assertEqual(args['namespace'], 'name')
        args = parse_args(["--namespace", "name", "file", "list"])
        self.assertEqual(args['namespace'], 'name')

        args = parse_args(['-b', 'bucket', 'file', 'list'])
        self.assertEqual(args['bucket_name'], 'bucket')
        args = parse_args(['--bucket-name', 'bucket', 'file', 'list'])
        self.assertEqual(args['bucket_name'], 'bucket')

    def test_file(self):
        with self.assertRaises(CLIException) as error:
            args = parse_args(['file'])
        self.assertEqual("Missing args: No command provided", str(error.exception))

    def test_file_list(self):
        args = parse_args(["file", "list"])
        self.assertEqual(args.pop('module'), "file")
        self.assertEqual(args.pop('command'), "list")

    def test_file_md5(self):
        with self.assertRaises(CLIException) as error:
            parse_args(["file", "md5"])
        self.assertEqual("the following arguments are required: local_file", str(error.exception))

        args = parse_args(["file", "md5", "foo"])
        self.assertEqual(args.pop('module'), "file")
        self.assertEqual(args.pop('command'), "md5")
        self.assertEqual(args['local_file'], "foo")

    def test_file_backup(self):
        with self.assertRaises(CLIException) as error:
            parse_args(["file", "backup"])
        self.assertEqual("the following arguments are required: local_file", str(error.exception))

        args = parse_args(["file", "backup", "path"])
        self.assertEqual(args['module'], 'file')
        self.assertEqual(args['command'], 'backup')
        self.assertEqual(args['local_file'], 'path')
        self.assertEqual(args['overwrite'], False)

        args = parse_args(["file", "backup", "path", '--overwrite'])
        self.assertEqual(args['module'], 'file')
        self.assertEqual(args['command'], 'backup')
        self.assertEqual(args['local_file'], 'path')
        self.assertEqual(args['overwrite'], True)

    def test_file_restore(self):
        with self.assertRaises(CLIException) as error:
            parse_args(["file", "restore"])
        self.assertEqual("the following arguments are required: local_file_id", str(error.exception))

    # TODO test backup
    # TODO test settings file loads
