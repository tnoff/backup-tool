from argparse import ArgumentParser

from backup_tool.exception import CLIException


class CommonArgparse(ArgumentParser):
    '''
    Common argparse for other functions to inherit
    '''
    def error(self, message):
        '''
        Return error message
        '''
        raise CLIException(message)
