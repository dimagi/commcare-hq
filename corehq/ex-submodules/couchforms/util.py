# coding: utf-8
from __future__ import absolute_import

import logging
from StringIO import StringIO

from couchdbkit import ResourceNotFound
from django.test.client import Client

from corehq.util.soft_assert import soft_assert
from corehq.util.test_utils import unit_testing_only
from dimagi.utils.couch.undo import DELETED_SUFFIX
from .exceptions import UnexpectedDeletedXForm
from .models import (
    XFormInstance,
    doc_types,
)

legacy_notification_assert = soft_assert(notify_admins=True, exponential_backoff=False)


def fetch_and_wrap_form(doc_id):
    # This logic is independent of couchforms; when it moves elsewhere,
    # please use the most appropriate alternative to get a DB handle.

    db = XFormInstance.get_db()
    doc = db.get(doc_id)
    if doc['doc_type'] in doc_types():
        return doc_types()[doc['doc_type']].wrap(doc)
    if doc['doc_type'] == "%s%s" % (XFormInstance.__name__, DELETED_SUFFIX):
        raise UnexpectedDeletedXForm(doc_id)
    raise ResourceNotFound(doc_id)


@unit_testing_only
def spoof_submission(submit_url, body):
    client = Client()
    f = StringIO(body.encode('utf-8'))
    f.name = 'form.xml'
    response = client.post(submit_url, {
        'xml_submission_file': f,
    })
    try:
        return response['X-CommCareHQ-FormID']
    except KeyError:
        return None
