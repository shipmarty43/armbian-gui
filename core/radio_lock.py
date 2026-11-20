"""Process ownership shared with the Zero 2W LoRaWAN service."""
import fcntl
import os
import stat

LOCK_PATH = '/run/lock/opi-radio.lock'


def acquire_radio():
    fd = os.open(LOCK_PATH, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise OSError('Invalid SX1262 lock file')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
