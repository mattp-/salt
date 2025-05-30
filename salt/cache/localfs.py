"""
Cache data in filesystem.

.. versionadded:: 2016.11.0

The ``localfs`` Minion cache module is the default cache module and does not
require any configuration.

Expiration values can be set in the relevant config file (``/etc/salt/master`` for
the master, ``/etc/salt/cloud`` for Salt Cloud, etc).
"""

import errno
import logging
import os
import os.path
import shutil
import tempfile

import salt.payload
import salt.utils.atomicfile
import salt.utils.files
import salt.utils.path
from salt.exceptions import SaltCacheError

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}


def __cachedir(kwargs=None):
    if kwargs and "cachedir" in kwargs:
        return kwargs["cachedir"]
    return __opts__.get("cachedir", salt.syspaths.CACHE_DIR)


def init_kwargs(kwargs):
    return {"cachedir": __cachedir(kwargs)}


def get_storage_id(kwargs):
    return ("localfs", __cachedir(kwargs))


def store(bank, key, data, cachedir):
    """
    Store information in a file.
    """
    base = salt.utils.path.join(cachedir, os.path.normpath(bank))
    try:
        os.makedirs(base)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise SaltCacheError(
                f"The cache directory, {base}, could not be created: {exc}"
            )

    outfile = salt.utils.path.join(base, f"{key}.p")
    tmpfh, tmpfname = tempfile.mkstemp(dir=base)
    os.close(tmpfh)
    try:
        with salt.utils.files.fopen(tmpfname, "w+b") as fh_:
            salt.payload.dump(data, fh_)
        # On Windows, os.rename will fail if the destination file exists.
        salt.utils.atomicfile.atomic_rename(tmpfname, outfile)
    except OSError as exc:
        raise SaltCacheError(
            f"There was an error writing the cache file, {base}: {exc}"
        )


def fetch(bank, key, cachedir):
    """
    Fetch information from a file.
    """
    inkey = False
    key_file = salt.utils.path.join(cachedir, os.path.normpath(bank), f"{key}.p")
    if not os.path.isfile(key_file):
        # The bank includes the full filename, and the key is inside the file
        key_file = salt.utils.path.join(cachedir, os.path.normpath(bank) + ".p")
        inkey = True

    if not os.path.isfile(key_file):
        log.debug('Cache file "%s" does not exist', key_file)
        return {}
    try:
        with salt.utils.files.fopen(key_file, "rb") as fh_:
            if inkey:
                return salt.payload.load(fh_)[key]
            else:
                return salt.payload.load(fh_)
    except OSError as exc:
        raise SaltCacheError(
            f'There was an error reading the cache file "{key_file}": {exc}'
        )


def updated(bank, key, cachedir):
    """
    Return the epoch of the mtime for this cache file
    """
    key_file = salt.utils.path.join(cachedir, os.path.normpath(bank), f"{key}.p")
    if not os.path.isfile(key_file):
        log.warning('Cache file "%s" does not exist', key_file)
        return None
    try:
        return int(os.path.getmtime(key_file))
    except OSError as exc:
        raise SaltCacheError(
            f'There was an error reading the mtime for "{key_file}": {exc}'
        )


def flush(bank, key=None, cachedir=None):
    """
    Remove the key from the cache bank with all the key content.
    """
    if cachedir is None:
        cachedir = __cachedir()

    try:
        if key is None:
            target = salt.utils.path.join(cachedir, os.path.normpath(bank))
            if not os.path.isdir(target):
                return False
            shutil.rmtree(target)
        else:
            target = salt.utils.path.join(cachedir, os.path.normpath(bank), f"{key}.p")
            if not os.path.isfile(target):
                return False
            os.remove(target)
    except OSError as exc:
        raise SaltCacheError(f'There was an error removing "{target}": {exc}')
    return True


def list_(bank, cachedir):
    """
    Return an iterable object containing all entries stored in the specified bank.
    """
    base = salt.utils.path.join(cachedir, os.path.normpath(bank))
    if not os.path.isdir(base):
        return []
    try:
        items = os.listdir(base)
    except OSError as exc:
        raise SaltCacheError(f'There was an error accessing directory "{base}": {exc}')
    ret = []
    for item in items:
        if item.endswith(".p"):
            ret.append(item.rstrip(item[-2:]))
        else:
            ret.append(item)
    return ret


def contains(bank, key, cachedir):
    """
    Checks if the specified bank contains the specified key.
    """
    if key is None:
        base = salt.utils.path.join(cachedir, os.path.normpath(bank))
        return os.path.isdir(base)
    else:
        keyfile = salt.utils.path.join(cachedir, os.path.normpath(bank), f"{key}.p")
        return os.path.isfile(keyfile)
