from __future__ import absolute_import
from __future__ import unicode_literals

import errno
import os
import os.path

from django.conf import settings

from corehq.apps.tzmigration.planning import DiffDB


def init_state_db(domain):
    db_filepath = _get_state_db_filepath(domain)
    return DiffDB.init(db_filepath)


def open_state_db(domain):
    db_filepath = _get_state_db_filepath(domain)
    return DiffDB.open(db_filepath)


def delete_state_db(domain):
    db_filepath = _get_state_db_filepath(domain)
    try:
        os.remove(db_filepath)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def _get_state_db_filepath(domain):
    return os.path.join(settings.SHARED_DRIVE_CONF.tzmigration_planning_dir,
                        '{}-tzmigration.db'.format(domain))
