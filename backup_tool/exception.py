class BackupToolException(Exception):
    '''
    Generic Exception for all backup tool functions
    '''
    pass

class ObjectStorageException(BackupToolException):
    '''
    Exception specific to object storage options
    '''
    pass

class CLIException(BackupToolException):
    '''
    Exception specific to cli actions
    '''
    pass

class BackupToolClientException(BackupToolException):
    '''
    Generic exception for client
    '''
    pass
