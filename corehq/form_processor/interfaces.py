from couchdbkit import ResourceNotFound
from casexml.apps.case.dbaccessors import get_reverse_indices_for_case_id
from casexml.apps.case.util import get_case_xform_ids, post_case_blocks
from casexml.apps.phone.models import SyncLog
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.util.test_utils import unit_testing_only

from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.couch.database import iter_docs, safe_delete
from casexml.apps.case.models import CommCareCase
from couchforms.util import process_xform
from couchforms.models import doc_types, XFormInstance, XFormError
from couchforms.exceptions import UnexpectedDeletedXForm

from .exceptions import CaseNotFound, XFormNotFound
from .utils import to_generic


class FormProcessorInterface(object):
    """
    The FormProcessorInterface serves as the base transactions that take place in forms. Different
    backends can implement this class in order to make common interface.
    """

    @staticmethod
    @to_generic
    def create_from_generic(generic_xform, generic_attachment=None):
        xform = XFormInstance.from_generic(generic_xform)
        xform.save()
        if generic_attachment:
            xform.put_attachment(**generic_attachment.to_json())
        return xform

    @staticmethod
    @to_generic
    def create_case_from_generic(generic_case):
        case = CommCareCase.from_generic(generic_case)
        case.save()
        return case

    @staticmethod
    def get_attachment(xform_id, attachment_name):
        return XFormInstance.get_db().fetch_attachment(xform_id, attachment_name)

    @classmethod
    def archive_xform(cls, xform_generic, user=None):
        xform = cls._get_xform(xform_generic.id)
        return xform.archive(user=user)

    @classmethod
    def unarchive_xform(cls, xform_generic, user=None):
        xform = cls._get_xform(xform_generic.id)
        return xform.unarchive(user=user)

    @classmethod
    def get_xml_element(cls, xform_generic):
        xform = cls._get_xform(xform_generic.id)
        return xform.get_xml_element()

    @classmethod
    @to_generic
    def get_xform(cls, xform_id):
        try:
            return cls._get_xform(xform_id)
        except ResourceNotFound:
            raise XFormNotFound

    @staticmethod
    def _get_xform(xform_id):
        db = XFormInstance.get_db()
        doc = db.get(xform_id)
        if doc['doc_type'] in doc_types():
            return doc_types()[doc['doc_type']].wrap(doc)
        if doc['doc_type'] == "%s%s" % (XFormInstance.__name__, DELETED_SUFFIX):
            raise UnexpectedDeletedXForm(xform_id)
        raise ResourceNotFound(xform_id)

    @classmethod
    @to_generic
    def get_case(cls, case_id):
        try:
            return cls._get_case(case_id)
        except ResourceNotFound:
            raise CaseNotFound

    @staticmethod
    def _get_case(case_id):
        return CommCareCase.get(case_id)

    @staticmethod
    @to_generic
    def get_cases(case_ids):
        return [
            CommCareCase.wrap(doc) for doc in iter_docs(
                CommCareCase.get_db(),
                case_ids
            )
        ]

    @staticmethod
    def get_cases_in_domain(domain):
        case_ids = FormProcessorInterface.get_case_ids_in_domain(domain)
        return FormProcessorInterface.get_cases(case_ids)

    @staticmethod
    def get_case_ids_in_domain(domain):
        return get_case_ids_in_domain(domain)

    @staticmethod
    def get_reverse_indices(domain, case_id):
        return get_reverse_indices_for_case_id(domain, case_id)

    @staticmethod
    @to_generic
    def get_by_doc_type(domain, doc_type):
        return XFormError.view(
            'domain/docs',
            startkey=[domain, doc_type],
            endkey=[domain, doc_type, {}],
            reduce=False,
            include_docs=True,
        ).all()

    @classmethod
    @to_generic
    def update_properties(cls, xform_generic, **properties):
        xform = cls._get_xform(xform_generic.id)
        for prop, value in properties.iteritems():
            setattr(xform, prop, value)
        xform.save()
        return xform

    @classmethod
    @to_generic
    def update_case_properties(cls, case_generic, **properties):
        case = cls._get_case(case_generic.id)
        for prop, value in properties.iteritems():
            setattr(case, prop, value)
        case.save()
        return case

    @staticmethod
    def get_case_xform_ids_from_couch(case_id):
        return get_case_xform_ids(case_id)

    @staticmethod
    @to_generic
    @unit_testing_only
    def post_xform(instance_xml, attachments=None, process=None, domain='test-domain'):
        """
        create a new xform and releases the lock

        this is a testing entry point only and is not to be used in real code

        """
        if not process:
            def process(xform):
                xform.domain = domain
        xform_lock = process_xform(instance_xml, attachments=attachments, process=process, domain=domain)
        with xform_lock as xforms:
            for xform in xforms:
                xform.save()
            return xforms[0]

    @staticmethod
    def submit_form_locally(instance, domain='test-domain', **kwargs):
        from corehq.apps.receiverwrapper.util import submit_form_locally
        response, xform, cases = submit_form_locally(instance, domain, **kwargs)
        # response is an iterable to @to_generic doesn't work
        return response, xform.to_generic(), [case.to_generic() for case in cases]

    @staticmethod
    @to_generic
    def post_case_blocks(case_blocks, form_extras=None, domain=None):
        return post_case_blocks(case_blocks, form_extras=form_extras, domain=domain)

    @classmethod
    def soft_delete_case(cls, case_id):
        case = cls._get_case(case_id)
        case.doc_type += DELETED_SUFFIX
        case.save()

    @classmethod
    def hard_delete_case(cls, case_generic):
        from casexml.apps.case.cleanup import safe_hard_delete
        case = cls._get_case(case_generic.id)
        safe_hard_delete(case)

    @classmethod
    @unit_testing_only
    def delete_all_cases(cls):
        cls._delete_all(CommCareCase.get_db(), 'case/get_lite')

    @classmethod
    @unit_testing_only
    def delete_all_xforms(cls):
        cls._delete_all(XFormInstance.get_db(), 'couchforms/all_submissions_by_domain')

    @classmethod
    @unit_testing_only
    def delete_all_sync_logs(cls):
        cls._delete_all(SyncLog.get_db(), 'phone/sync_logs_by_user')

    @staticmethod
    def _delete_all(db, viewname):
        deleted = set()
        for row in db.view(viewname, reduce=False):
            doc_id = row['id']
            if id not in deleted:
                try:
                    safe_delete(db, doc_id)
                    deleted.add(doc_id)
                except ResourceNotFound:
                    pass
