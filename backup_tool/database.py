from sqlalchemy import Column, ForeignKey, Integer, String, Float
from sqlalchemy.orm import declarative_base


# taken from https://www.reddit.com/r/Python/comments/4kqdyg/cool_sqlalchemy_trick/
def as_dict(self):
    '''
    Return database entry as dictionary
    '''
    new_data = {}
    data = self.__dict__
    for key, value in data.items():
        if not key.startswith("_") and not hasattr(value, "__call__"):
            new_data[key] = data[key]
    return new_data

def inject_function(func):
    '''
    Inject function into database table as decorator
    '''
    def decorated_class(cls):
        setattr(cls, func.__name__, func)
        return cls
    return decorated_class

BASE = declarative_base()

# Assume that every unique file is only uploaded once ( to minimize space )
# but that each unique file can be in many places on file systems ( ...thanks windows and your lack of symlinks )

@inject_function(as_dict)
class BackupEntry(BASE):
    '''
    BackupEntry, uploaded copy of file
    '''
    __tablename__ = 'backup_entry'

    # Primary key
    id = Column(Integer, primary_key=True)

    # File paths
    uploaded_file_path = Column(String(256), unique=True)

    # Original md5 sum before encryption
    original_md5_checksum = Column(String(32))

    # MD5 sums
    uploaded_md5_checksum = Column(String(32), unique=True)

@inject_function(as_dict)
class BackupEntryLocalFile(BASE):
    '''
    BackupEntryLocalFile, local copy of file
    '''
    __tablename__ = 'backup_entry_local_file'

    # Primary key
    id = Column(Integer, primary_key=True)

    # Foreign Key to backup entry
    backup_entry_id = Column(Integer, ForeignKey('backup_entry.id'))

    # Local Path
    local_file_path = Column(String(40960), unique=True)

    # Cached metadata for fast change detection
    cached_mtime = Column(Float, nullable=True)
    cached_size = Column(Integer, nullable=True)
