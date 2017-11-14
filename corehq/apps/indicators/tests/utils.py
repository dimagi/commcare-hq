from __future__ import absolute_import
from corehq.apps.indicators.utils import (INDICATOR_CONFIG_DOC_ID,
    INDICATOR_CONFIG_LOCK_KEY, get_indicator_config)
from corehq.util.test_utils import unit_testing_only
from couchdbkit import ResourceNotFound
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.database import get_db


@unit_testing_only
def delete_indicator_doc():
    with CriticalSection([INDICATOR_CONFIG_LOCK_KEY]):
        try:
            get_db().delete_doc(INDICATOR_CONFIG_DOC_ID)
            get_indicator_config.clear()
        except ResourceNotFound:
            pass
