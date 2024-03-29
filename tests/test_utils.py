from tempfile import TemporaryDirectory

from backup_tool import utils


def test_md5():
    '''
    Run md5 and make sure it matches expected
    '''
    # Hardcoded, this is what the base64 hash of foo is
    value = '07BzhNET7exJ6qYjitX/AA=='
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as temp:
            with open(temp, 'w') as writer:
                writer.write('foo\n')
            md5_value = utils.md5(temp)
        assert md5_value == value, 'MD5 value not equal to expected'

def test_setup_logger():
    '''
    Test basic logging to file
    '''
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as temp:
            log = utils.setup_logger('test', 10, logging_file=temp)
        log.debug(f'Running log test with log file {temp}')
