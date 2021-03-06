# -------------------------------------------------------------------------
#                     The CodeChecker Infrastructure
#   This file is distributed under the University of Illinois Open Source
#   License. See LICENSE.TXT for details.
# -------------------------------------------------------------------------
"""
Check host machine for a compile command logger.
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import errno
import os
import subprocess

from libcodechecker.logger import get_logger

LOG = get_logger('system')


def check_intercept(env):
    """
    Simple check if intercept (scan-build-py) is available.
    """
    intercept_cmd = ['intercept-build', '--help']
    try:
        with open(os.devnull, 'wb') as null:
            res = subprocess.check_call(intercept_cmd,
                                        env=env,
                                        stdout=null,
                                        stderr=null)

        if not res:
            return True
        else:
            LOG.debug('Failed to run: "%s"', ' '.join(intercept_cmd))
            return False
    except subprocess.CalledProcessError:
        LOG.debug('Failed to run: "%s", process returned non-zero exit code.',
                  ' '.join(intercept_cmd))
        return False
    except OSError as oerr:
        if oerr.errno == errno.ENOENT:
            # Not just intercept-build can be used for logging.
            # It is possible that another build logger is available.
            LOG.debug(oerr)
            LOG.debug('Failed to run: "%s"', ' '.join(intercept_cmd))
            return False
