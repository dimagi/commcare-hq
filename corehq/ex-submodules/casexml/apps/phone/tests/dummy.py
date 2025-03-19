from datetime import datetime
from casexml.apps.phone.models import OTARestoreWebUser
from casexml.apps.case.xml.generator import date_to_xml_string

DUMMY_ID = "foo"
DUMMY_USERNAME = "mclovin"
DUMMY_PASSWORD = "changeme"
DUMMY_PROJECT = "domain"


def dummy_user_xml(user=None):
    username = user.username if user else DUMMY_USERNAME
    password = user.password if user else DUMMY_PASSWORD
    user_id = user.user_id if user else DUMMY_ID
    date_joined = user.date_joined if user else datetime.utcnow()
    project = user.domain if user else DUMMY_PROJECT
    user_type = 'web' if isinstance(user, OTARestoreWebUser) else 'commcare'

    return f"""
    <Registration xmlns="http://openrosa.org/user/registration">
        <username>{username}</username>
        <password>{password}</password>
        <uuid>{user_id}</uuid>
        <date>{date_to_xml_string(date_joined)}</date>
        <user_data>
            <data key="commcare_first_name"/>
            <data key="commcare_last_name"/>
            <data key="commcare_phone_number"/>
            <data key="commcare_profile"/>
            <data key="commcare_project">{project}</data>
            <data key="commcare_user_type">{user_type}</data>
            <data key="something">arbitrary</data>
        </user_data>
    </Registration>"""


def dummy_restore_xml(restore_id, case_xml="", items=None, user=None):
    items_xml = '' if items is None else f' items="{items}"'
    return f"""
    <OpenRosaResponse xmlns="http://openrosa.org/http/response"{items_xml}>
        <message nature="ota_restore_success">Successfully restored account mclovin!</message>
        <Sync xmlns="http://commcarehq.org/sync">
            <restore_id>{restore_id}</restore_id>
        </Sync>
        {dummy_user_xml(user)}
        {case_xml}
    </OpenRosaResponse>
    """
