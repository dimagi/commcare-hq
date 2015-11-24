# coding: utf-8
from __future__ import absolute_import

import logging
from StringIO import StringIO

from couchdbkit import ResourceNotFound
from django.test.client import Client

from corehq.util.soft_assert import soft_assert
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


def spoof_submission(submit_url, body, name="form.xml", hqsubmission=True,
                     headers=None):
    if headers is None:
        headers = {}
    client = Client()
    f = StringIO(body.encode('utf-8'))
    f.name = name
    response = client.post(submit_url, {
        'xml_submission_file': f,
    }, **headers)
    if hqsubmission:
        xform_id = response['X-CommCareHQ-FormID']
        xform = XFormInstance.get(xform_id)
        xform['doc_type'] = "HQSubmission"
        xform.save()
    return response
