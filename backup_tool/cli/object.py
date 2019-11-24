import json
import os
import sys


from backup_tool.exception import CLIException
from backup_tool.oci_client import ObjectStorageClient
from backup_tool.cli.common import CommonArgparse

DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser('~'),
                                   '.oci',
                                   'config')

def parse_args(args):
    parser = CommonArgparse(description="Object Storage CLI")
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

    # Object Get
    object_get = object_sub_parser.add_parser("get", help="Object Get")
    object_get.add_argument("namespace_name", help="Namespace Name")
    object_get.add_argument("bucket_name", help="Bucket Name")
    object_get.add_argument("object_name", help="Object Name")
    object_get.add_argument("file_name", help="File Name")

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
