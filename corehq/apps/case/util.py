import os
import uuid
from corehq.apps.app_manager.util import format_time

with open(os.path.join(os.path.dirname(__file__), "data", "close.xml")) as f:
    _close_case_template = f.read()


with open(os.path.join(os.path.dirname(__file__), "data", "close_referral.xml")) as f:
    _close_referral_template = f.read()

def get_close_case_xml(time, case_id, uid=None):
    if not uid:
        uid = uuid.uuid4().hex
    time = format_time(time)
    return _close_case_template % (locals())

def get_close_referral_xml(time, case_id, referral_id, referral_type, uid=None):
    if not uid:
        uid = uuid.uuid4().hex
    time = format_time(time)
    return _close_referral_template % (locals())