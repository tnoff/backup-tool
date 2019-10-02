#!/usr/bin/env python

from argparse import ArgumentParser
import re

from backup_tool.exception import CLIException


class CommonArgparse(ArgumentParser):
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

