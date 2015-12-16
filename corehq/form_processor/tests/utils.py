import functools
from uuid import uuid4

from couchdbkit import ResourceNotFound
from datetime import datetime

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.models import SyncLog
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.interfaces.processor import FormProcessorInterface, ProcessedForms
from corehq.form_processor.parsers.form import process_xform_xml
from couchforms.models import XFormInstance
from dimagi.ext import jsonobject
from dimagi.utils.couch.database import safe_delete
from corehq.util.test_utils import unit_testing_only, run_with_multiple_configs, RunConfig
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL, CaseTransaction, Attachment
from django.conf import settings


class FormProcessorTestUtils(object):

    @classmethod
    @unit_testing_only
    def delete_all_cases(cls, domain=None):
        assert CommCareCase.get_db().dbname.endswith('test')
        view_kwargs = {}
        if domain:
            view_kwargs = {
                'startkey': [domain],
                'endkey': [domain, {}],
            }

        cls._delete_all(
            CommCareCase.get_db(),
            'cases_by_server_date/by_server_modified_on',
            **view_kwargs
        )

        def _sql_delete(query, domain_filter):
            if domain is not None:
                query.filter(domain_filter)
            query.all().delete()

        FormProcessorTestUtils.delete_all_sql_cases(domain)

    @staticmethod
    def delete_all_sql_cases(domain=None):
        CaseAccessorSQL.delete_all_cases(domain)

    @classmethod
    @unit_testing_only
    def delete_all_xforms(cls, domain=None, user_id=None):
        view = 'couchforms/all_submissions_by_domain'
        view_kwargs = {}
        if domain and user_id:
            view = 'reports_forms/all_forms'
            view_kwargs = {
                'startkey': ['submission user', domain, user_id],
                'endkey': ['submission user', domain, user_id, {}],

            }
        elif domain:
            view_kwargs = {
                'startkey': [domain],
                'endkey': [domain, {}]
            }

        cls._delete_all(
            XFormInstance.get_db(),
            view,
            **view_kwargs
        )

        FormProcessorTestUtils.delete_all_sql_forms(domain, user_id)

    @staticmethod
    def delete_all_sql_forms(domain=None, user_id=None):
        FormAccessorSQL.delete_all_forms(domain, user_id)

    @classmethod
    @unit_testing_only
    def delete_all_sync_logs(cls):
        cls._delete_all(SyncLog.get_db(), 'phone/sync_logs_by_user')

    @staticmethod
    @unit_testing_only
    def _delete_all(db, viewname, **view_kwargs):
        deleted = set()
        for row in db.view(viewname, reduce=False, **view_kwargs):
            doc_id = row['id']
            if id not in deleted:
                try:
                    safe_delete(db, doc_id)
                    deleted.add(doc_id)
                except ResourceNotFound:
                    pass


run_with_all_backends = functools.partial(
    run_with_multiple_configs,
    run_configs=[
        # run with default setting
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_SQL_BACKEND': getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False),
            },
            post_run=lambda *args, **kwargs: args[0].tearDown()
        ),
        # run with inverse of default setting
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_SQL_BACKEND': not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False),
            },
            pre_run=lambda *args, **kwargs: args[0].setUp(),
        ),
    ]
)


@unit_testing_only
def post_xform(instance_xml, attachments=None, domain='test-domain'):
    """
    create a new xform and releases the lock

    this is a testing entry point only and is not to be used in real code

    """
    result = process_xform_xml(domain, instance_xml, attachments=attachments)
    with result.get_locked_forms() as xforms:
        FormProcessorInterface(domain).save_processed_models(xforms)
        return xforms[0]


def create_form_for_test(domain, case_id=None, attachments=None, save=True):
    """
    Create the models directly so that these tests aren't dependent on any
    other apps. Not testing form processing here anyway.
    :param case_id: create case with ID if supplied
    :param attachments: additional attachments dict
    :param save: if False return the unsaved form
    :return: form object
    """
    form_id = uuid4().hex
    user_id = 'user1'
    utcnow = datetime.utcnow()

    form_xml = get_simple_form_xml(form_id, case_id)

    form = XFormInstanceSQL(
        form_id=form_id,
        xmlns='http://openrosa.org/formdesigner/form-processor',
        received_on=utcnow,
        user_id=user_id,
        domain=domain
    )

    attachments = attachments or {}
    attachment_tuples = map(
        lambda a: Attachment(name=a[0], raw_content=a[1], content_type=a[1].content_type),
        attachments.items()
    )
    attachment_tuples.append(Attachment('form.xml', form_xml, 'text/xml'))

    FormProcessorSQL.store_attachments(form, attachment_tuples)

    cases = []
    if case_id:
        case = CommCareCaseSQL(
            case_id=case_id,
            domain=domain,
            type='',
            owner_id=user_id,
            opened_on=utcnow,
            modified_on=utcnow,
            modified_by=user_id,
            server_modified_on=utcnow,
        )
        case.track_create(CaseTransaction.form_transaction(case, form))
        cases = [case]

    if save:
        FormProcessorSQL.save_processed_models(ProcessedForms(form, None), cases)
    return form


SIMPLE_FORM = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="{form_name}" xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns="{xmlns}">
    <dalmation_count>yes</dalmation_count>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>DEV IL</n1:deviceID>
        <n1:timeStart>2013-04-19T16:52:41.000-04</n1:timeStart>
        <n1:timeEnd>{time_end}</n1:timeEnd>
        <n1:username>eve</n1:username>
        <n1:userID>{user_id}</n1:userID>
        <n1:instanceID>{uuid}</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms"></n2:appVersion>
    </n1:meta>
    {case_block}
</data>"""


class TestFormMetadata(jsonobject.JsonObject):
    domain = jsonobject.StringProperty(required=False)
    xmlns = jsonobject.StringProperty(default='http://openrosa.org/formdesigner/form-processor')
    form_name = jsonobject.StringProperty(default='New Form')
    user_id = jsonobject.StringProperty(default='cruella_deville')
    time_end = jsonobject.DateTimeProperty(default=datetime(2013, 4, 19, 16, 53, 2))
    # Set this property to fake the submission time
    received_on = jsonobject.DateTimeProperty(default=datetime.utcnow())


def get_simple_form_xml(form_id, case_id=None, metadata=None):
    metadata = metadata or TestFormMetadata()
    case_block = ''
    if case_id:
        case_block = CaseBlock(create=True, case_id=case_id).as_string()
    form_xml = SIMPLE_FORM.format(uuid=form_id, case_block=case_block, **metadata.to_json())
    return form_xml
