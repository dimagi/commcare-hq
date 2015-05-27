from dimagi.utils.decorators.memoized import memoized


@memoized
def get_dbs_for_public_docs():
    return _get_dbs(public__in=(True,))


@memoized
def get_dbs_for_all_docs():
    return _get_dbs(public__in=(True, False))


def _get_dbs(public__in):
    from casexml.apps.case.models import CommCareCase
    from corehq.apps.app_manager.models import Application, RemoteApp
    from corehq.apps.fixtures.models import FixtureDataType
    from corehq.apps.registration.models import RegistrationRequest
    from corehq.apps.reminders.models import CaseReminderHandler
    from corehq.apps.sms.models import MessageLog, SMSLog
    from corehq.apps.users.models import CommCareUser, UserRole
    from couchforms.models import XFormInstance
    from couchlog.models import ExceptionRecord

    doc_types_to_public = {
        ExceptionRecord: False,
        MessageLog: False,
        RegistrationRequest: False,
        SMSLog: False,
        XFormInstance: False,
        CommCareUser: False,
        CommCareCase: False,
        UserRole: True,
        Application: True,
        RemoteApp: True,
        CaseReminderHandler: True,
        FixtureDataType: True
    }

    dbs = {}
    for doc_type, public in doc_types_to_public.items():
        if public in public__in:
            db = doc_type.get_db()
            dbs[db.server_uri, db.dbname] = db
    return dbs.values()


def get_public_documents_related_to_domain(domain):
    for db in get_dbs_for_public_docs():
        for res in db.view('domain/related_to_domain', key=[domain, True]):
            yield res['value']['_id'], res['value']['doc_type']


def get_all_documents_related_to_domain(domain):
    for db in get_dbs_for_all_docs():
        for res in db.view('domain/related_to_domain',
                           startkey=[domain],
                           endkey=[domain, {}]):
            yield res['value']['_id'], res['value']['doc_type']
