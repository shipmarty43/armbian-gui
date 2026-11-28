"""Process ownership for one logical CS on the Zero 2W header controller."""
import fcntl
import os
from pathlib import Path
import stat

# Keep CS0 on the inode already used by LoRaWAN, Meshtastic and Reticulum.
LOCK_PATH = '/run/lock/opi-radio.lock'


def acquire_radio(cs=0):
    if type(cs) is not int or not 0 <= cs < 4:
        raise ValueError("Expected a Zero 2W SPI1 chip select (0..3)")
    path = Path(LOCK_PATH)
    if cs:
        path = path.with_name(f"opi-spi1-cs{cs}.lock")
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise OSError(f'Invalid SPI1 CS{cs} lock file')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
