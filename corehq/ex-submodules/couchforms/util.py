from __future__ import absolute_import
import hashlib
import datetime
import logging
import pytz

from StringIO import StringIO
from django.test.client import Client

from couchdbkit import ResourceNotFound, BulkSaveError
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
import iso8601
from redis import ConnectionError
from corehq.apps.tzmigration import phone_timezones_should_be_processed
from dimagi.ext.jsonobject import re_loose_datetime
from dimagi.utils.couch.undo import DELETED_SUFFIX

from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch import uid, LockManager, ReleaseOnError
from dimagi.utils.parsing import json_format_datetime
import xml2json

import couchforms
from . import const
from .exceptions import DuplicateError, UnexpectedDeletedXForm
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
    ReceiverResult,
    successful_form_received,
)
from .xml import ResponseNature, OpenRosaResponse


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


def _extract_meta_instance_id(form):
    """Takes form json (as returned by xml2json)"""
    if form.get('Meta'):
        # bhoma, 0.9 commcare
        meta = form['Meta']
    elif form.get('meta'):
        # commcare 1.0
        meta = form['meta']
    else:
        return None

    if meta.get('uid'):
        # bhoma
        return meta['uid']
    elif meta.get('instanceID'):
        # commcare 0.9, commcare 1.0
        return meta['instanceID']
    else:
        return None


def convert_xform_to_json(xml_string):
    """
    takes xform payload as xml_string and returns the equivalent json
    i.e. the json that will show up as xform.form

    """

    try:
        name, json_form = xml2json.xml2json(xml_string)
    except xml2json.XMLSyntaxError as e:
        raise couchforms.XMLSyntaxError(u'Invalid XML: %s' % e)
    json_form['#type'] = name
    return json_form


def acquire_lock_for_xform(xform_id):
    # this is high, but I want to test if MVP conflicts disappear
    lock = XFormInstance.get_obj_lock_by_id(xform_id, timeout_seconds=2*60)
    try:
        lock.acquire()
    except ConnectionError:
        lock = None
    return lock


class MultiLockManager(list):
    def __enter__(self):
        return [lock_manager.__enter__() for lock_manager in self]

    def __exit__(self, exc_type, exc_val, exc_tb):
        for lock_manager in self:
            lock_manager.__exit__(exc_type, exc_val, exc_tb)


def adjust_datetimes(data, parent=None, key=None):
    """
    find all datetime-like strings within data (deserialized json)
    and format them uniformly, in place.

    """
    # this strips the timezone like we've always done
    # todo: in the future this will convert to UTC
    if isinstance(data, basestring) and re_loose_datetime.match(data):
        try:
            matching_datetime = iso8601.parse_date(data)
        except iso8601.ParseError:
            pass
        else:
            if phone_timezones_should_be_processed():
                parent[key] = json_format_datetime(
                    matching_datetime.astimezone(pytz.utc).replace(tzinfo=None)
                )
            else:
                parent[key] = json_format_datetime(
                    matching_datetime.replace(tzinfo=None))

    elif isinstance(data, dict):
        for key, value in data.items():
            adjust_datetimes(value, parent=data, key=key)
    elif isinstance(data, list):
        for i, value in enumerate(data):
            adjust_datetimes(value, parent=data, key=i)

    # return data, just for convenience in testing
    # this is the original input, modified, not a new data structure
    return data


def create_xform(xml_string, attachments=None, _id=None, process=None):
    """
    create but do not save an XFormInstance from an xform payload (xml_string)
    optionally set the doc _id to a predefined value (_id)
    return doc _id of the created doc

    `process` is transformation to apply to the form right before saving
    This is to avoid having to save multiple times

    If xml_string is bad xml
      - raise couchforms.XMLSyntaxError

    """
    from corehq.util.couch_helpers import CouchAttachmentsBuilder

    assert attachments is not None
    json_form = convert_xform_to_json(xml_string)
    adjust_datetimes(json_form)

    _id = (_id or _extract_meta_instance_id(json_form)
           or XFormInstance.get_db().server.next_uuid())
    assert _id
    attachments_builder = CouchAttachmentsBuilder()
    attachments_builder.add(
        content=xml_string,
        name='form.xml',
        content_type='text/xml',
    )

    for key, value in attachments.items():
        attachments_builder.add(
            content=value,
            name=key,
            content_type=value.content_type,
        )

    xform = XFormInstance(
        # form has to be wrapped
        {'form': json_form},
        # other properties can be set post-wrap
        _id=_id,
        xmlns=json_form.get('@xmlns'),
        _attachments=attachments_builder.to_json(),
        received_on=datetime.datetime.utcnow(),
    )

    # this had better not fail, don't think it ever has
    # if it does, nothing's saved and we get a 500
    if process:
        process(xform)

    lock = acquire_lock_for_xform(_id)
    with ReleaseOnError(lock):
        if _id in XFormInstance.get_db():
            raise DuplicateError()

    return LockManager(xform, lock)


def process_xform(instance, attachments=None, process=None, domain=None,
                  _id=None):
    """
    Create a new xform to ready to be saved to couchdb in a thread-safe manner
    Returns a LockManager containing the new XFormInstance and its lock,
    or raises an exception if anything goes wrong.

    attachments is a dictionary of the request.FILES that are not the xform;
    key is parameter name, value is django MemoryFile object stream

    """
    attachments = attachments or {}

    try:
        xform_lock = create_xform(instance, process=process,
                                  attachments=attachments, _id=_id)
    except couchforms.XMLSyntaxError as e:
        xform = _log_hard_failure(instance, attachments, e)
        raise SubmissionError(xform)
    except DuplicateError:
        return _handle_id_conflict(instance, attachments, process=process,
                                   domain=domain)
    return MultiLockManager([xform_lock])


def _has_errors(response, errors):
    return errors or "error" in response


def _extract_id_from_raw_xml(xml):
    # the code this is replacing didn't deal with the error either
    # presumably because it's already been run once by the time it gets here
    _, json_form = xml2json.xml2json(xml)
    return _extract_meta_instance_id(json_form) or ''


def _handle_id_conflict(instance, attachments, process, domain):
    """
    For id conflicts, we check if the files contain exactly the same content,
    If they do, we just log this as a dupe. If they don't, we deprecate the
    previous form and overwrite it with the new form's contents.
    """

    assert domain
    conflict_id = _extract_id_from_raw_xml(instance)

    existing_doc = XFormInstance.get_db().get(conflict_id, attachments=True)
    if existing_doc.get('domain') != domain or existing_doc.get('doc_type') not in doc_types():
        # the same form was submitted to two domains, or a form was submitted with
        # an ID that belonged to a different doc type. these are likely developers
        # manually testing or broken API users. just resubmit with a generated ID.
        return process_xform(instance, attachments=attachments,
                             process=process, _id=uid.new())
    else:
        # It looks like a duplicate/edit in the same domain so pursue that workflow.
        existing_doc = XFormInstance.wrap(existing_doc)
        return _handle_duplicate(existing_doc, instance, attachments, process)


def _handle_duplicate(existing_doc, instance, attachments, process):
    """
    Handle duplicate xforms and xform editing ('deprecation')

    existing doc *must* be validated as an XFormInstance in the right domain
    and *must* include inline attachments

    """
    conflict_id = existing_doc.get_id
    existing_md5 = existing_doc.xml_md5()
    new_md5 = hashlib.md5(instance).hexdigest()

    if existing_md5 != new_md5:
        # if the form contents are not the same:
        #  - "Deprecate" the old form by making a new document with the same contents
        #    but a different ID and a doc_type of XFormDeprecated
        #  - Save the new instance to the previous document to preserve the ID

        old_id = existing_doc._id
        new_id = XFormInstance.get_db().server.next_uuid()

        multi_lock_manager = process_xform(instance, attachments=attachments,
                                           process=process, _id=new_id)
        [(xform, _)] = multi_lock_manager

        # swap the two documents so the original ID now refers to the new one
        # and mark original as deprecated
        xform._id, existing_doc._id = old_id, new_id
        xform._rev, existing_doc._rev = existing_doc._rev, xform._rev

        # flag the old doc with metadata pointing to the new one
        existing_doc.doc_type = deprecation_type()
        existing_doc.orig_id = old_id

        # and give the new doc server data of the old one and some metadata
        xform.received_on = existing_doc.received_on
        xform.deprecated_form_id = existing_doc._id
        xform.edited_on = datetime.datetime.utcnow()

        multi_lock_manager.append(
            LockManager(existing_doc,
                        acquire_lock_for_xform(old_id))
        )
        return multi_lock_manager
    else:
        # follow standard dupe handling, which simply saves a copy of the form
        # but a new doc_id, and a doc_type of XFormDuplicate
        new_doc_id = uid.new()
        new_form, lock = create_xform(instance, attachments=attachments,
                                      _id=new_doc_id, process=process)

        new_form.doc_type = XFormDuplicate.__name__
        dupe = XFormDuplicate.wrap(new_form.to_json())
        dupe.problem = "Form is a duplicate of another! (%s)" % conflict_id
        return MultiLockManager([LockManager(dupe, lock)])


def is_deprecation(xform):
    return xform.doc_type == deprecation_type()


def deprecation_type():
    return XFormDeprecated.__name__


def is_override(xform):
    # it's an override if we've explicitly set the "deprecated_form_id" property on it.
    return bool(getattr(xform, 'deprecated_form_id', None))


def _log_hard_failure(instance, attachments, error):
    """
    Handle's a hard failure from posting a form to couch.

    Currently, it will save the raw payload to couch in a hard-failure doc
    and return that doc.
    """
    try:
        message = unicode(error)
    except UnicodeDecodeError:
        message = unicode(str(error), encoding='utf-8')

    return SubmissionErrorLog.from_instance(instance, message)


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

    def _attach_shared_props(self, doc):
        # attaches shared properties of the request to the document.
        # used on forms and errors
        doc.auth_context = self.auth_context.to_json()
        doc.submit_ip = self.submit_ip
        doc.path = self.path

        doc.openrosa_headers = self.openrosa_headers
        doc.last_sync_token = self.last_sync_token

        if self.received_on:
            doc.received_on = self.received_on

        if self.date_header:
            doc.date_header = self.date_header

        doc.domain = self.domain
        doc.app_id = self.app_id
        doc.build_id = self.build_id
        doc.export_tag = ["domain", "xmlns"]

        return doc

    def run(self):
        if not self.auth_context.is_valid():
            return self.failed_auth_response, None, []

        if isinstance(self.instance, const.BadRequest):
            return HttpResponseBadRequest(self.instance.message), None, []

        def process(xform):
            self._attach_shared_props(xform)
            scrub_meta(xform)

        try:
            lock_manager = process_xform(self.instance,
                                         attachments=self.attachments,
                                         process=process,
                                         domain=self.domain)
        except SubmissionError as e:
            logging.exception(
                u"Problem receiving submission to %s. %s" % (
                    self.path,
                    unicode(e),
                )
            )
            return self.get_exception_response(e.error_log), None, []
        else:
            from casexml.apps.case.models import CommCareCase
            from casexml.apps.case.xform import (
                get_and_check_xform_domain, CaseDbCache, process_cases_with_casedb
            )
            from casexml.apps.case.signals import case_post_save
            from casexml.apps.case.exceptions import IllegalCaseId, UsesReferrals
            from corehq.apps.commtrack.processing import process_stock
            from corehq.apps.commtrack.exceptions import MissingProductId

            cases = []
            responses = []
            errors = []
            with lock_manager as xforms:
                instance = xforms[0]
                if instance.doc_type == 'XFormInstance':
                    if len(xforms) > 1:
                        assert len(xforms) == 2
                        assert is_deprecation(xforms[1])
                    domain = get_and_check_xform_domain(instance)
                    with CaseDbCache(domain=domain, lock=True, deleted_ok=True, xforms=xforms) as case_db:
                        try:
                            case_result = process_cases_with_casedb(xforms, case_db)
                            stock_result = process_stock(instance, case_db)
                        except (IllegalCaseId, UsesReferrals, MissingProductId) as e:
                            # errors we know about related to the content of the form
                            # log the error and respond with a success code so that the phone doesn't
                            # keep trying to send the form
                            instance = _handle_known_error(e, instance)
                            xforms[0] = instance
                            # this is usually just one document, but if an edit errored we want
                            # to save the deprecated form as well
                            XFormInstance.get_db().bulk_save(xforms)
                            response = self._get_open_rosa_response(instance,
                                                                    None, None)
                            return response, instance, cases
                        except Exception as e:
                            # handle / log the error and reraise so the phone knows to resubmit
                            # note that in the case of edit submissions this won't flag the previous
                            # submission as having been edited. this is intentional, since we should treat
                            # this use case as if the edit "failed"
                            instance = _handle_unexpected_error(e, instance)
                            instance.save()
                            raise
                        now = datetime.datetime.utcnow()
                        unfinished_submission_stub = UnfinishedSubmissionStub(
                            xform_id=instance.get_id,
                            timestamp=now,
                            saved=False,
                            domain=domain,
                        )
                        unfinished_submission_stub.save()
                        cases = case_db.get_changed()
                        # todo: this property is useless now
                        instance.initial_processing_complete = True
                        assert XFormInstance.get_db().uri == CommCareCase.get_db().uri
                        docs = xforms + cases

                        # in saving the cases, we have to do all the things
                        # done in CommCareCase.save()
                        for case in cases:
                            case.initial_processing_complete = True
                            case.server_modified_on = now
                            try:
                                rev = CommCareCase.get_db().get_rev(case.case_id)
                            except ResourceNotFound:
                                pass
                            else:
                                assert rev == case.get_rev, (
                                    "Aborting because there would have been "
                                    "a document update conflict. {} {} {}".format(
                                        case.get_id, case.get_rev, rev
                                    )
                                )
                        try:
                            # save both the forms and cases
                            XFormInstance.get_db().bulk_save(docs)
                        except BulkSaveError as e:
                            logging.error('BulkSaveError saving forms', exc_info=1,
                                          extra={'details': {'errors': e.errors}})
                            raise
                        unfinished_submission_stub.saved = True
                        unfinished_submission_stub.save()
                        case_result.commit_dirtiness_flags()
                        stock_result.commit()
                        for case in cases:
                            case_post_save.send(CommCareCase, case=case)

                    responses, errors = self.process_signals(instance)
                    if errors:
                        # .problems was added to instance
                        instance.save()
                    unfinished_submission_stub.delete()
                elif instance.doc_type == 'XFormDuplicate':
                    assert len(xforms) == 1
                    instance.save()
            response = self._get_open_rosa_response(instance, responses, errors)
            return response, instance, cases

    def get_response(self):
        response, _, _ = self.run()
        return response

    @staticmethod
    def process_signals(instance):
        feedback = successful_form_received.send_robust(None, xform=instance)
        responses = []
        errors = []
        for func, resp in feedback:
            if resp and isinstance(resp, Exception):
                error_message = unicode(resp)
                logging.error((
                    u"Receiver app: problem sending "
                    u"post-save signal %s for xform %s: %s: %s"
                ) % (func, instance._id, type(resp).__name__, error_message))
                errors.append(error_message)
            elif resp and isinstance(resp, ReceiverResult):
                responses.append(resp)
        if errors:
            instance.problem = ", ".join(errors)
        return responses, errors

    @staticmethod
    def get_failed_auth_response():
        return HttpResponseForbidden('Bad auth')

    def _get_open_rosa_response(self, instance, responses, errors):
        if instance.doc_type == "XFormInstance":
            response = self.get_success_response(instance, responses, errors)
        else:
            response = self.get_failure_response(instance)

        # this hack is required for ODK
        response["Location"] = self.location

        # this is a magic thing that we add
        response['X-CommCareHQ-FormID'] = instance.get_id
        return response

    @staticmethod
    def get_success_response(doc, responses, errors):

        if errors:
            response = OpenRosaResponse(
                message=doc.problem,
                nature=ResponseNature.SUBMIT_ERROR,
                status=201,
            ).response()
        elif responses:
            # use the response with the highest priority if we got any
            responses.sort()
            response = HttpResponse(responses[-1].response, status=201)
        else:
            # default to something generic
            response = OpenRosaResponse(
                message="Thanks for submitting!",
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

    def get_exception_response(self, error_log):
        error_doc = SubmissionErrorLog.get(error_log.get_id)
        self._attach_shared_props(error_doc)
        error_doc.save()
        return OpenRosaResponse(
            message=("The sever got itself into big trouble! "
                     "Details: %s" % error_log.problem),
            nature=ResponseNature.SUBMIT_ERROR,
            status=500,
        ).response()


def _handle_known_error(e, instance):
    error_message = '{}: {}'.format(
        type(e).__name__, unicode(e))
    logging.exception((
        u"Warning in case or stock processing "
        u"for form {}: {}."
    ).format(instance._id, error_message))
    instance.__class__ = XFormError
    instance.doc_type = 'XFormError'
    instance.problem = error_message
    return instance


def _handle_unexpected_error(e, instance):
    # Some things to consider here
    # The following code saves the xform instance
    # as an XFormError, with a different ID.
    # That's because if you save with the original ID
    # and then resubmit, the new submission never has a
    # chance to get reprocessed; it'll just get saved as
    # a duplicate.
    error_message = '{}: {}'.format(
        type(e).__name__, unicode(e))
    new_id = XFormError.get_db().server.next_uuid()
    logging.exception((
        u"Error in case or stock processing "
        u"for form {}: {}.\n"
        u"Error saved as {}"
    ).format(instance._id, error_message, new_id))
    instance.__class__ = XFormError
    instance.orig_id = instance._id
    instance._id = new_id
    if '_rev' in instance:
        # clear the rev since we want to make a new doc
        # this is necessary for errors that come from editing submissions
        del instance['_rev']
    instance.problem = error_message
    return instance


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
