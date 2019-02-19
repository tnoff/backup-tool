#!/usr/bin/env python

from argparse import ArgumentParser
import json
import os
import re
import sys

from backup_tool.exception import CLIException
from backup_tool.oci_client import ObjectStorageClient


DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser('~'),
                                   '.oci',
                                   'config')

class BackupToolArgparse(ArgumentParser):
    def error(self, message):
        '''
        Some logic here to keep the error printing consistent
        If theres a cli arg that contains "invalid choice: '<whatever>' (choose from 'opt1', 'opt2')"
        Make sure the options are presented in alphabetical order
        '''
        CHOICE_REGEX = ".* invalid choice: '[a-zA-Z]+' \(choose from (.*)\)"
        result = re.match(CHOICE_REGEX, message)
        if result:
            options = result.group(1)
            OPTIONS_REGEX = "'([a-zA-Z0-9]+)'"
            options_list = sorted(re.findall(OPTIONS_REGEX, options))
            sorted_output = ", ".join("'%s'" % opt for opt in options_list)
            message = message.replace(options, sorted_output)
        raise CLIException(message)

def parse_args(args):
    parser = BackupToolArgparse(description="Object Storage CLI")
    parser.add_argument("-c", "--config-file", default=DEFAULT_CONFIG_PATH,
                        help="OCI Config File")
    parser.add_argument("-s", "--config-stage", default="DEFAULT",
                        help="OCI Config Stage")

    # Sub parsers
    sub_parser = parser.add_subparsers(dest="module", description="Sub-modules")
    object_parser = sub_parser.add_parser("object", help="Object Module")

    # Object Arguments
    object_sub_parser = object_parser.add_subparsers(dest="command", description="Command")

    # Object List
    object_list = object_sub_parser.add_parser("list", help="Object List")
    object_list.add_argument("namespace_name", help="Namespace Name")
    object_list.add_argument("bucket_name", help="Bucket Name")

    # Object Put
    object_put = object_sub_parser.add_parser("put", help="Object Put")
    object_put.add_argument("namespace_name", help="Namespace Name")
    object_put.add_argument("bucket_name", help="Bucket Name")
    object_put.add_argument("object_name", help="Object Name")
    object_put.add_argument("file_name", help="File Name")

    # Final Steps
    parsed_args = vars(parser.parse_args(args))

    if not parsed_args['module']:
        raise CLIException("Missing args: No module provided")

    if not parsed_args['command']:
        raise CLIException("Missing args: No command provided")

    return parsed_args

class ObjectCLI():
    def __init__(self, **kwargs):
        self.client = ObjectStorageClient(kwargs.pop('config_file'),
                                          kwargs.pop('config_stage'))

        command = getattr(self.client,
                          "%s_%s" % (kwargs.pop('module'), kwargs.pop('command')))
        value = command(**kwargs)
        if value is not None:
            print(json.dumps(value, indent=4))

def main():
    args = parse_args(sys.argv[1:])
    ObjectCLI(**args)

if __name__ == '__main__':
    main()
