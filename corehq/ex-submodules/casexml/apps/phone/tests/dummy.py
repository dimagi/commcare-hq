from datetime import datetime
from casexml.apps.phone.models import OTARestoreWebUser
from casexml.apps.case.xml.generator import date_to_xml_string

DUMMY_ID = "foo"
DUMMY_USERNAME = "mclovin"
DUMMY_PASSWORD = "changeme"
DUMMY_PROJECT = "domain"

LOCATION_IDS_DATA_FIELDS = """
                              <data key="commcare_location_id"/>
                              <data key="commcare_location_ids"/>"""
COMMCARE_PRIMARY_CASE_SHARING_ID = """
                                      <data key="commcare_primary_case_sharing_id"/>"""


def dummy_user_xml(user=None):
    username = user.username if user else DUMMY_USERNAME
    password = user.password if user else DUMMY_PASSWORD
    user_id = user.user_id if user else DUMMY_ID
    date_joined = user.date_joined if user else datetime.utcnow()
    project = user.domain if user else DUMMY_PROJECT
    user_type = 'web' if isinstance(user, OTARestoreWebUser) else 'commcare'

    return """
    <Registration xmlns="http://openrosa.org/user/registration">
        <username>{}</username>
        <password>{}</password>
        <uuid>{}</uuid>
        <date>{}</date>
        <user_data>
            <data key="commcare_first_name"/>
            <data key="commcare_last_name"/>{}
            <data key="commcare_phone_number"/>{}
            <data key="commcare_profile"/>
            <data key="commcare_project">{}</data>
            <data key="commcare_user_type">{}</data>
            <data key="something">arbitrary</data>
        </user_data>
    </Registration>""".format(
        username,
        password,
        user_id,
        date_to_xml_string(date_joined),
        LOCATION_IDS_DATA_FIELDS if user_type == 'web' else '',
        COMMCARE_PRIMARY_CASE_SHARING_ID if user_type == 'web' else '',
        project,
        user_type,
    )

DUMMY_RESTORE_XML_TEMPLATE = ("""
<OpenRosaResponse xmlns="http://openrosa.org/http/response"%(items_xml)s>
    <message nature="ota_restore_success">%(message)s</message>
    <Sync xmlns="http://commcarehq.org/sync">
        <restore_id>%(restore_id)s</restore_id>
    </Sync>
    %(user_xml)s
    %(case_xml)s
</OpenRosaResponse>
""")


def dummy_restore_xml(restore_id, case_xml="", items=None, user=None):
    return DUMMY_RESTORE_XML_TEMPLATE % {
        "restore_id": restore_id,
        "items_xml": '' if items is None else (' items="%s"' % items),
        "user_xml": dummy_user_xml(user),
        "case_xml": case_xml,
        "message": "Successfully restored account mclovin!"
    }
