import os
import uuid
from couchdbkit.schema.properties import LazyDict

with open(os.path.join(os.path.dirname(__file__), "data", "close.xml")) as f:
    _close_case_template = f.read()


with open(os.path.join(os.path.dirname(__file__), "data", "close_referral.xml")) as f:
    _close_referral_template = f.read()


def format_time(time):
    # this was copied from app_manager.util in the migration
    # it's a silly thing to have there and here.
    return time.strftime("%Y-%m-%dT%H:%M:%SZ")

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

def couchable_property(prop):
    """
    Sometimes properties that come from couch can't be put back in
    without some modification.
    """
    if isinstance(prop, LazyDict):
        return dict(prop)
    return prop
            