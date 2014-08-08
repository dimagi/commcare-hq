import time
import requests
from requests.auth import HTTPBasicAuth
from hq_settings import HQTransaction
from datetime import datetime
import uuid
import os
from django.core.files.uploadedfile import UploadedFile
from random import random, sample

try:
    from localsettings import URL_TEMPLATE
except ImportError:
    URL_TEMPLATE = '/a/{domain}/receiver/secure/'

REQUEST_TIMEOUT = 100

SUBMIT_TEMPLATE = """<?xml version='1.0'?>
<data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="http://www.commcarehq.org/loadtest">
    <meta>
        <deviceID>multimechanize</deviceID>
        <timeStart>%(timestart)s</timeStart>
        <timeEnd>%(timeend)s</timeEnd>
        <username>multimechanize</username>
        <userID>multimechanize</userID>
        <instanceID>%(instanceid)s</instanceID>
    </meta>
    %(extras)s
</data>"""

CREATE_CASE_TEMPLATE = """
<case xmlns="http://commcarehq.org/case/transaction/v2" case_id="%(caseid)s"
        date_modified="%(moddate)s" user_id="multimechanize">
    <create>
        <case_type_id>loadtest</case_type_id>
        <case_name>load test case</case_name>
    </create>
    <update>
        <prop1>val1</prop1>
        <prop2>val2</prop2>
    </update>
</case>
"""

UPDATE_CASE_TEMPLATE = """
<case xmlns="http://commcarehq.org/case/transaction/v2" case_id="%(caseid)s"
        date_modified="%(moddate)s" user_id="multimechanize">
    <update>
        <prop1>val1</prop1>
        <prop2>val2</prop2>
    </update>
</case>
"""

ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

with open(os.path.join(os.path.dirname(__file__), "data", "5kb.xml")) as f:
    LONG_FORM_DATA = f.read()

PIC_NAME = "picture"
PIC_PATH = os.path.join(os.path.dirname(__file__), "data", "sphynx.jpg")


def _format_datetime(time_t):
    return time_t.strftime(ISO_FORMAT)


def _submission(extras=''):
    return SUBMIT_TEMPLATE % {
        'timestart': _format_datetime(datetime.utcnow()),
        'timeend': _format_datetime(datetime.utcnow()),
        'instanceid': uuid.uuid4().hex,
        'extras': extras,
    }

CASE_IDS = set()

def _case_block(action="create"):
    TMPL = {"create": CREATE_CASE_TEMPLATE,
            "update": UPDATE_CASE_TEMPLATE}[action]
    if action == 'create':
        caseid = uuid.uuid4().hex
    else:
        caseid = sample(CASE_IDS, 1)[0]
        CASE_IDS.remove(caseid)

    caseblock = TMPL % {
        'moddate': _format_datetime(datetime.utcnow()),
        'caseid': caseid,
    }
    return caseblock, caseid

def _attachmentFileStream(key):
    attachment_path = PIC_PATH
    attachment = open(attachment_path, 'rb')
    uf = UploadedFile(attachment, key)
    return uf

def _prepAttachments():
    attachment_block = '<attachment><%s src="%s" from="local"/></attachment>' %(PIC_NAME, PIC_PATH)
    dict_attachments = {PIC_NAME: _attachmentFileStream(PIC_NAME)}
    return attachment_block, dict_attachments


class Transaction(HQTransaction):
    """
    Out of 15 forms:
        - 5 should create a new case
        - 10 should update a case
        - 12 should include multimedia

    """
    def __init__(self):
        self.url_template = URL_TEMPLATE
        super(Transaction, self).__init__()

    def _normal_submit(self, url, data):
        headers = {
            'content-type': 'text/xml',
            'content-length': len(data),
        }
        return requests.post(
            url,
            data=data,
            headers=headers,
            auth=HTTPBasicAuth(self.submissions_username, self.submissions_password),
            timeout=REQUEST_TIMEOUT,
        )

    def _media_submit(self, url, data_dict):
        return requests.post(
            url,
            files=data_dict,
            auth=HTTPBasicAuth(self.submissions_username, self.submissions_password),
            timeout=REQUEST_TIMEOUT,
        )

    def do_submission(self, url, include_image, case_action):
        extras = LONG_FORM_DATA  # 5k filler

        block, caseid = _case_block(action=case_action)
        extras += block

        if not include_image:
            data = _submission(extras=extras)
            submit_fn = self._normal_submit
        else:
            attachment_block, dict_attachments = _prepAttachments()
            data = {"xml_submission_file": _submission(extras=attachment_block+extras)}
            data.update(dict_attachments)
            submit_fn = self._media_submit

        start_timer = time.time()
        resp = submit_fn(url, data)
        return start_timer, resp, caseid

    @property
    def url(self):
        return self.url_template.format(domain=self.domain)

    def run(self):
        include_image = random() < 12/15
        if CASE_IDS:  # if there are no caseids to update, just create some
            case_action = "update" if random() > 5/15 else "create"
        else:
            case_action = "create"
        url = '%s%s' % (self.base_url, self.url)
        start_timer, resp, caseid = self.do_submission(url, include_image, case_action)
        latency = time.time() - start_timer
        self.custom_timers['submission'] = latency
        responsetext = resp.text
        CASE_IDS.add(caseid)
        assert resp.status_code == 201, (
            "Bad HTTP Response", resp.status_code, url
        )
        assert "Thanks for submitting" in responsetext, "Bad response text"

if __name__ == '__main__':
    trans = Transaction()
    trans.run()
    print trans.custom_timers
