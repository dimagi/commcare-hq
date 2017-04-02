from mock import MagicMock
from datetime import date, datetime
from casexml.apps.case.xml.generator import date_to_xml_string

DUMMY_ID = "foo"
DUMMY_USERNAME = "mclovin"
DUMMY_PASSWORD = "changeme"
DUMMY_PROJECT = "domain"


def dummy_user():
    return MagicMock(
        username=DUMMY_USERNAME,
        password=DUMMY_PASSWORD,
        user_id=DUMMY_ID,
        date_joined=date(2016, 12, 12),
        user_session_data={
            'first_name': 'mclovin',
            'last_name': None,
            'phone_number': '555555',
            'something': 'arbitrary',
        }
    )


def dummy_user_xml(user=None):
    username = user.username if user else DUMMY_USERNAME
    password = user.password if user else DUMMY_PASSWORD
    user_id = user.user_id if user else DUMMY_ID
    date_joined = user.date_joined if user else datetime.utcnow()
    project = user.domain if user else DUMMY_PROJECT

    return """
    <Registration xmlns="http://openrosa.org/user/registration">
        <username>{}</username>
        <password>{}</password>
        <uuid>{}</uuid>
        <date>{}</date>
        <user_data>
            <data key="commcare_project">{}</data>
            <data key="commcare_last_name"/>
            <data key="commcare_phone_number"/>
            <data key="something">arbitrary</data>
            <data key="commcare_first_name"/>
        </user_data>
    </Registration>""".format(
        username,
        password,
        user_id,
        date_to_xml_string(date_joined),
        project
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
