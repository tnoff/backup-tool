class BackupToolException(Exception):
    pass

class ObjectStorageException(BackupToolException):
    pass

class CLIException(BackupToolException):
    pass
