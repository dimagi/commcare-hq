# coding: utf-8
from __future__ import absolute_import
import hashlib
import datetime
import logging
from StringIO import StringIO

from django.test.client import Client
from couchdbkit import ResourceNotFound
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from corehq.apps.tzmigration import timezone_migration_in_progress
from corehq.form_processor.utils import new_xform, acquire_lock_for_xform
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.logging import notify_exception
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch import LockManager
import couchforms
from .const import BadRequest
from .exceptions import DuplicateError, UnexpectedDeletedXForm, \
    PhoneDateValueError
from .models import (
    DefaultAuthContext,
    SubmissionErrorLog,
    UnfinishedSubmissionStub,
    XFormDeprecated,
    XFormDuplicate,
    XFormError,
    XFormInstance,
    doc_types,
)
from .signals import (
    successful_form_received,
)
from .xml import ResponseNature, OpenRosaResponse

legacy_soft_assert = soft_assert('{}@{}'.format('skelly', 'dimagi.com'))

class SubmissionError(Exception, UnicodeMixIn):
    """
    When something especially bad goes wrong during a submission, this
    exception gets raised.
    """

    def __init__(self, error_log, *args, **kwargs):
        super(SubmissionError, self).__init__(*args, **kwargs)
        self.error_log = error_log
    
    def __str__(self):
        return str(self.error_log)


class MultiLockManager(list):
    def __enter__(self):
        return [lock_manager.__enter__() for lock_manager in self]

    def __exit__(self, exc_type, exc_val, exc_tb):
        for lock_manager in self:
            lock_manager.__exit__(exc_type, exc_val, exc_tb)


def process_xform(instance, attachments=None, process=None, domain=None):
    """
    Create a new xform to ready to be saved to couchdb in a thread-safe manner
    Returns a LockManager containing the new XFormInstance and its lock,
    or raises an exception if anything goes wrong.

    attachments is a dictionary of the request.FILES that are not the xform;
    key is parameter name, value is django MemoryFile object stream

    """
    attachments = attachments or {}

    try:
        xform_lock = new_xform(instance, process=process, attachments=attachments)
    except couchforms.XMLSyntaxError as e:
        xform = _log_hard_failure(instance, process, e)
        raise SubmissionError(xform)
    except DuplicateError as e:
        return _handle_id_conflict(instance, e.xform, domain)
    return MultiLockManager([xform_lock])


def _has_errors(response, errors):
    return errors or "error" in response


def _assign_new_id_and_lock(xform):
    new_id = XFormInstance.get_db().server.next_uuid()
    xform._id = new_id
    lock = acquire_lock_for_xform(new_id)
    return MultiLockManager([LockManager(xform, lock)])


def assign_new_id(xform):
    new_id = XFormInstance.get_db().server.next_uuid()
    xform._id = new_id
    return xform


def deprecate_xform(existing_doc, new_doc):
    # if the form contents are not the same:
    #  - "Deprecate" the old form by making a new document with the same contents
    #    but a different ID and a doc_type of XFormDeprecated
    #  - Save the new instance to the previous document to preserve the ID

    old_id = existing_doc._id
    new_doc = assign_new_id(new_doc)

    # swap the two documents so the original ID now refers to the new one
    # and mark original as deprecated
    new_doc._id, existing_doc._id = old_id, new_doc._id
    new_doc._rev, existing_doc._rev = existing_doc._rev, new_doc._rev

    # flag the old doc with metadata pointing to the new one
    existing_doc.doc_type = deprecation_type()
    existing_doc.orig_id = old_id

    # and give the new doc server data of the old one and some metadata
    new_doc.received_on = existing_doc.received_on
    new_doc.deprecated_form_id = existing_doc._id
    new_doc.edited_on = datetime.datetime.utcnow()
    return existing_doc, new_doc


def deduplicate_xform(new_doc):
    # follow standard dupe handling, which simply saves a copy of the form
    # but a new doc_id, and a doc_type of XFormDuplicate
    new_doc.doc_type = XFormDuplicate.__name__
    dupe = XFormDuplicate.wrap(new_doc.to_json())
    dupe.problem = "Form is a duplicate of another! (%s)" % new_doc._id
    return assign_new_id(dupe)


def is_duplicate_or_edit(xform_id, domain):
    existing_doc = XFormInstance.get_db().get(xform_id)
    return existing_doc.get('domain') == domain and existing_doc.get('doc_type') in doc_types()


def _handle_id_conflict(instance, xform, domain):
    """
    For id conflicts, we check if the files contain exactly the same content,
    If they do, we just log this as a dupe. If they don't, we deprecate the
    previous form and overwrite it with the new form's contents.
    """

    assert domain
    conflict_id = xform._id

    if is_duplicate_or_edit(conflict_id, domain):
        # It looks like a duplicate/edit in the same domain so pursue that workflow.
        return _handle_duplicate(xform, instance)
    else:
        # the same form was submitted to two domains, or a form was submitted with
        # an ID that belonged to a different doc type. these are likely developers
        # manually testing or broken API users. just resubmit with a generated ID.
        return _assign_new_id_and_lock(xform)


def _handle_duplicate(new_doc, instance):
    """
    Handle duplicate xforms and xform editing ('deprecation')

    existing doc *must* be validated as an XFormInstance in the right domain
    and *must* include inline attachments

    """
    conflict_id = new_doc._id
    existing_doc = XFormInstance.get_db().get(conflict_id, attachments=True)
    existing_doc = XFormInstance.wrap(existing_doc)

    existing_md5 = existing_doc.xml_md5()
    new_md5 = hashlib.md5(instance).hexdigest()

    if existing_md5 != new_md5:
        # if the form contents are not the same:
        #  - "Deprecate" the old form by making a new document with the same contents
        #    but a different ID and a doc_type of XFormDeprecated
        #  - Save the new instance to the previous document to preserve the ID
        existing_doc, new_doc = deprecate_xform(existing_doc, new_doc)
        
        # Lock docs with their original ID's (before they got switched during deprecation)
        return MultiLockManager([
            LockManager(new_doc, acquire_lock_for_xform(existing_doc._id)),
            LockManager(existing_doc, acquire_lock_for_xform(existing_doc.orig_id)),
        ])
    else:
        # follow standard dupe handling, which simply saves a copy of the form
        # but a new doc_id, and a doc_type of XFormDuplicate
        duplicate = deduplicate_xform(new_doc)
        return MultiLockManager([
            LockManager(duplicate, acquire_lock_for_xform(duplicate._id)),
        ])


def is_deprecation(xform):
    return xform.doc_type == deprecation_type()


def deprecation_type():
    return XFormDeprecated.__name__


def is_override(xform):
    # it's an override if we've explicitly set the "deprecated_form_id" property on it.
    return bool(getattr(xform, 'deprecated_form_id', None))


def _log_hard_failure(instance, process, error):
    """
    Handle's a hard failure from posting a form to couch.

    Currently, it will save the raw payload to couch in a hard-failure doc
    and return that doc.
    """
    try:
        message = unicode(error)
    except UnicodeDecodeError:
        message = unicode(str(error), encoding='utf-8')

    error_log = SubmissionErrorLog.from_instance(instance, message)
    if process:
        process(error_log)

    error_log.save()
    return error_log


def scrub_meta(xform):
    """
    Cleans up old format metadata to our current standard.

    Does NOT save the doc, but returns whether the doc needs to be saved.
    """
    property_map = {'TimeStart': 'timeStart',
                    'TimeEnd': 'timeEnd',
                    'chw_id': 'userID',
                    'DeviceID': 'deviceID',
                    'uid': 'instanceID'}

    if not hasattr(xform, 'form'):
        return

    # hack to make sure uppercase meta still ends up in the right place
    found_old = False
    if 'Meta' in xform.form:
        xform.form['meta'] = xform.form['Meta']
        del xform.form['Meta']
        found_old = True
    if 'meta' in xform.form:
        meta_block = xform.form['meta']
        # scrub values from 0.9 to 1.0
        if isinstance(meta_block, list):
            if isinstance(meta_block[0], dict):
                # if it's a list of dictionaries, arbitrarily pick the first one
                # this is a pretty serious error, but it's also recoverable
                xform.form['meta'] = meta_block = meta_block[0]
                logging.error((
                    'form %s contains multiple meta blocks. '
                    'this is not correct but we picked one abitrarily'
                ) % xform.get_id)
            else:
                # if it's a list of something other than dictionaries.
                # don't bother scrubbing.
                logging.error('form %s contains a poorly structured meta block.'
                              'this might cause data display problems.')
        if isinstance(meta_block, dict):
            for key in meta_block:
                if key in property_map and property_map[key] not in meta_block:
                    meta_block[property_map[key]] = meta_block[key]
                    del meta_block[key]
                    found_old = True

    return found_old


class SubmissionPost(object):

    failed_auth_response = HttpResponseForbidden('Bad auth')

    def __init__(self, instance=None, attachments=None, auth_context=None,
                 domain=None, app_id=None, build_id=None, path=None,
                 location=None, submit_ip=None, openrosa_headers=None,
                 last_sync_token=None, received_on=None, date_header=None):
        assert domain, domain
        assert instance, instance
        assert not isinstance(instance, HttpRequest), instance
        self.domain = domain
        self.app_id = app_id
        self.build_id = build_id
        # get_location has good default
        self.location = location or couchforms.get_location()
        self.received_on = received_on
        self.date_header = date_header
        self.submit_ip = submit_ip
        self.last_sync_token = last_sync_token
        self.openrosa_headers = openrosa_headers or {}
        self.instance = instance
        self.attachments = attachments or {}
        self.auth_context = auth_context or DefaultAuthContext()
        self.path = path
        self.interface = FormProcessorInterface(domain)

    def _set_submission_properties(self, xform):
        # attaches shared properties of the request to the document.
        # used on forms and errors
        xform.auth_context = self.auth_context.to_json()
        xform.submit_ip = self.submit_ip
        xform.path = self.path

        xform.openrosa_headers = self.openrosa_headers
        xform.last_sync_token = self.last_sync_token

        if self.received_on:
            xform.received_on = self.received_on

        if self.date_header:
            xform.date_header = self.date_header

        xform.domain = self.domain
        xform.app_id = self.app_id
        xform.build_id = self.build_id
        xform.export_tag = ["domain", "xmlns"]
        return xform

    def _handle_known_error(self, error, instance, xforms):
        # errors we know about related to the content of the form
        # log the error and respond with a success code so that the phone doesn't
        # keep trying to send the form
        instance = _transform_instance_to_error(error, instance)
        xforms[0] = instance
        # this is usually just one document, but if an edit errored we want
        # to save the deprecated form as well
        self.interface.bulk_save(instance, xforms)
        return instance, [], []

    def _handle_basic_failure_modes(self):
        if timezone_migration_in_progress(self.domain):
            # keep submissions on the phone
            # until ready to start accepting again
            return HttpResponse(status=503), None, []

        if not self.auth_context.is_valid():
            return self.failed_auth_response, None, []

        if isinstance(self.instance, BadRequest):
            return HttpResponseBadRequest(self.instance.message), None, []

    def run(self):
        failure_result = self._handle_basic_failure_modes()
        if failure_result:
            return failure_result

        def process(xform):
            self._set_submission_properties(xform)
            if xform.doc_type != 'SubmissionErrorLog':
                found_old = scrub_meta(xform)
                legacy_soft_assert(not found_old, 'Form with old metadata submitted', xform.form_id)

        try:
            lock_manager = process_xform(self.instance,
                                         attachments=self.attachments,
                                         process=process,
                                         domain=self.domain)
        except SubmissionError as e:
            return self.get_exception_response_and_log(e, self.path), None, []
        else:
            instance, cases, errors = self.process_xforms_for_cases(lock_manager)
            response = self._get_open_rosa_response(instance, errors)
            return response, instance, cases

    def process_xforms_for_cases(self, xform_lock_manager):
        from casexml.apps.case.models import CommCareCase
        from casexml.apps.case.xform import (
            get_and_check_xform_domain, CaseDbCache, process_cases_with_casedb
        )
        from casexml.apps.case.signals import case_post_save
        from casexml.apps.case.exceptions import IllegalCaseId, UsesReferrals
        from corehq.apps.commtrack.processing import process_stock
        from corehq.apps.commtrack.exceptions import MissingProductId

        cases = []
        errors = []
        known_errors = (IllegalCaseId, UsesReferrals, MissingProductId,
                        PhoneDateValueError)
        with xform_lock_manager as xforms:
            instance = xforms[0]
            if self.validate_xforms_for_case_processing(xforms):
                domain = get_and_check_xform_domain(instance)
                with CaseDbCache(domain=domain, lock=True, deleted_ok=True, xforms=xforms) as case_db:
                    try:
                        case_result = process_cases_with_casedb(xforms, case_db)
                        stock_result = process_stock(xforms, case_db)
                    except known_errors as e:
                        return self._handle_known_error(e, instance, xforms)
                    except Exception as e:
                        # handle / log the error and reraise so the phone knows to resubmit
                        # note that in the case of edit submissions this won't flag the previous
                        # submission as having been edited. this is intentional, since we should treat
                        # this use case as if the edit "failed"
                        _handle_unexpected_error(instance, e)
                        raise

                    now = datetime.datetime.utcnow()
                    unfinished_submission_stub = UnfinishedSubmissionStub.objects.create(
                        xform_id=instance.get_id,
                        timestamp=now,
                        saved=False,
                        domain=domain,
                    )

                    # todo: this property is only used by the MVPFormIndicatorPillow
                    instance.initial_processing_complete = True

                    cases = case_db.get_cases_for_saving(now)

                    self.interface.bulk_save(instance, xforms, cases)

                    unfinished_submission_stub.saved = True
                    unfinished_submission_stub.save()
                    case_result.commit_dirtiness_flags()
                    stock_result.commit()
                    for case in cases:
                        case_post_save.send(CommCareCase, case=case)

                errors = self.process_signals(instance)
                unfinished_submission_stub.delete()

        return instance, cases, errors

    def get_response(self):
        response, _, _ = self.run()
        return response

    @staticmethod
    def process_signals(instance):
        feedback = successful_form_received.send_robust(None, xform=instance)
        errors = []
        for func, resp in feedback:
            if resp and isinstance(resp, Exception):
                error_message = unicode(resp)
                logging.error((
                    u"Receiver app: problem sending "
                    u"post-save signal %s for xform %s: %s: %s"
                ) % (func, instance._id, type(resp).__name__, error_message))
                errors.append(error_message)
        if errors:
            instance.problem = ", ".join(errors)
            instance.save()
        return errors

    @staticmethod
    def validate_xforms_for_case_processing(xforms):
        instance = xforms[0]
        if instance.is_duplicate:
            assert len(xforms) == 1
            instance.save()
            return False
        elif not instance.is_error:
            if len(xforms) > 1:
                assert len(xforms) == 2
                assert is_deprecation(xforms[1])
            return True

    @staticmethod
    def get_failed_auth_response():
        return HttpResponseForbidden('Bad auth')

    def _get_open_rosa_response(self, instance, errors):
        if instance.doc_type == "XFormInstance":
            response = self.get_success_response(instance, errors)
        else:
            response = self.get_failure_response(instance)

        # this hack is required for ODK
        response["Location"] = self.location

        # this is a magic thing that we add
        response['X-CommCareHQ-FormID'] = instance.get_id
        return response

    @staticmethod
    def get_success_response(doc, errors):

        if errors:
            response = OpenRosaResponse(
                message=doc.problem,
                nature=ResponseNature.SUBMIT_ERROR,
                status=201,
            ).response()
        else:
            response = OpenRosaResponse(
                # would have done ✓ but our test Nokias' fonts don't have that character
                message=u'   √   ',
                nature=ResponseNature.SUBMIT_SUCCESS,
                status=201,
            ).response()
        return response

    @staticmethod
    def get_failure_response(doc):
        return OpenRosaResponse(
            message=doc.problem,
            nature=ResponseNature.SUBMIT_ERROR,
            status=201,
        ).response()

    @staticmethod
    def get_exception_response_and_log(error, path):
        logging.exception(
            u"Problem receiving submission to %s. %s" % (
                path,
                unicode(error),
            )
        )
        return OpenRosaResponse(
            message=("The sever got itself into big trouble! "
                     "Details: %s" % error.error_log.problem),
            nature=ResponseNature.SUBMIT_ERROR,
            status=500,
        ).response()


def _transform_instance_to_error(e, instance):
    error_message = '{}: {}'.format(
        type(e).__name__, unicode(e))
    logging.exception((
        u"Warning in case or stock processing "
        u"for form {}: {}."
    ).format(instance._id, error_message))
    return XFormError.from_xform_instance(instance, error_message)


def _handle_unexpected_error(instance, e):
    # The following code saves the xform instance
    # as an XFormError, with a different ID.
    # That's because if you save with the original ID
    # and then resubmit, the new submission never has a
    # chance to get reprocessed; it'll just get saved as
    # a duplicate.
    error_message = u'{}: {}'.format(type(e).__name__, unicode(e))
    instance = XFormError.from_xform_instance(instance, error_message, with_new_id=True)
    notify_exception(None, (
        u"Error in case or stock processing "
        u"for form {}: {}. "
        u"Error saved as {}"
    ).format(instance.orig_id, error_message, instance._id))
    instance.save()


def fetch_and_wrap_form(doc_id):
    # This logic is independent of couchforms; when it moves elsewhere,
    # please use the most appropriate alternative to get a DB handle.

    db = XFormInstance.get_db()
    doc = db.get(doc_id)
    if doc['doc_type'] in doc_types():
        return doc_types()[doc['doc_type']].wrap(doc)
    if doc['doc_type'] == "%s%s" % (XFormInstance.__name__, DELETED_SUFFIX):
        raise UnexpectedDeletedXForm(doc_id)
    raise ResourceNotFound(doc_id)


def spoof_submission(submit_url, body, name="form.xml", hqsubmission=True,
                     headers=None):
    if headers is None:
        headers = {}
    client = Client()
    f = StringIO(body.encode('utf-8'))
    f.name = name
    response = client.post(submit_url, {
        'xml_submission_file': f,
    }, **headers)
    if hqsubmission:
        xform_id = response['X-CommCareHQ-FormID']
        xform = XFormInstance.get(xform_id)
        xform['doc_type'] = "HQSubmission"
        xform.save()
    return response
