import datetime
import uuid
from corehq.apps.receiverwrapper.util import get_submit_url
from dimagi.utils.parsing import json_format_datetime
from django.template.loader import render_to_string
from receiver.util import spoof_submission

def submit_case_blocks(case_blocks, domain):
    now = json_format_datetime(datetime.datetime.utcnow())
    if not isinstance(case_blocks, basestring):
        case_blocks = ''.join(case_blocks)
    form_xml = render_to_string('hqcase/xml/case_block.xml', {
        'case_block': case_blocks,
        'time': now,
        'uid': uuid.uuid4().hex
    })
    spoof_submission(
        get_submit_url(domain),
        form_xml,
    )
