# coding=utf-8
from __future__ import absolute_import

import contextlib
import datetime
import logging
from collections import namedtuple

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
import sys
import couchforms
from casexml.apps.case.exceptions import PhoneDateValueError, IllegalCaseId, UsesReferrals
from corehq.apps.commtrack.exceptions import MissingProductId
from corehq.apps.tzmigration import timezone_migration_in_progress
from corehq.form_processor.exceptions import CouchSaveAborted
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.parsers.form import process_xform_xml
from corehq.form_processor.utils.metadata import scrub_meta
from couchforms.const import BadRequest, DEVICE_LOG_XMLNS
from couchforms.models import DefaultAuthContext, UnfinishedSubmissionStub
from couchforms.signals import successful_form_received
from couchforms.util import legacy_notification_assert
from couchforms.openrosa_response import OpenRosaResponse, ResponseNature
from dimagi.utils.logging import notify_exception
from phonelog.utils import process_device_log


CaseStockProcessingResult = namedtuple(
    'CaseStockProcessingResult',
    'case_result, case_models, stock_result'
)


class SubmissionPost(object):

    failed_auth_response = HttpResponseForbidden('Bad auth')

    def __init__(self, instance=None, attachments=None, auth_context=None,
                 domain=None, app_id=None, build_id=None, path=None,
                 location=None, submit_ip=None, openrosa_headers=None,
                 last_sync_token=None, received_on=None, date_header=None,
                 partial_submission=False):
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
        self.formdb = FormAccessors(domain)
        self.partial_submission = partial_submission

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

        xform.app_id = self.app_id
        xform.build_id = self.build_id
        xform.export_tag = ["domain", "xmlns"]
        xform.partial_submission = self.partial_submission
        return xform

    def _handle_known_error(self, error, instance, xforms):
        # errors we know about related to the content of the form
        # log the error and respond with a success code so that the phone doesn't
        # keep trying to send the form
        instance = _transform_instance_to_error(self.interface, error, instance)
        xforms[0] = instance
        # this is usually just one document, but if an edit errored we want
        # to save the deprecated form as well
        self.interface.save_processed_models(xforms)

    def _handle_basic_failure_modes(self):
        if timezone_migration_in_progress(self.domain):
            # keep submissions on the phone
            # until ready to start accepting again
            return HttpResponse(status=503), None, []

        if not self.auth_context.is_valid():
            return self.failed_auth_response, None, []

        if isinstance(self.instance, BadRequest):
            return HttpResponseBadRequest(self.instance.message), None, []

    def _post_process_form(self, xform):
        self._set_submission_properties(xform)
        if xform.is_submission_error_log:
            found_old = scrub_meta(xform)
            legacy_notification_assert(not found_old, 'Form with old metadata submitted', xform.form_id)

    def run(self):
        failure_result = self._handle_basic_failure_modes()
        if failure_result:
            return failure_result

        result = process_xform_xml(self.domain, self.instance, self.attachments)
        submitted_form = result.submitted_form

        self._post_process_form(submitted_form)

        if submitted_form.is_submission_error_log:
            self.formdb.save_new_form(submitted_form)
            response = self.get_exception_response_and_log(submitted_form, self.path)
            return response, None, []

        cases = []
        with result.get_locked_forms() as xforms:
            instance = xforms[0]
            if instance.xmlns == DEVICE_LOG_XMLNS:
                try:
                    process_device_log(self.domain, instance)
                except Exception:
                    notify_exception(None, "Error processing device log", details={
                        'xml': self.instance,
                        'domain': self.domain
                    })
                    raise

            elif instance.is_duplicate:
                self.interface.save_processed_models([instance])
            elif not instance.is_error:
                try:
                    case_stock_result = self.process_xforms_for_cases(xforms)
                except (IllegalCaseId, UsesReferrals, MissingProductId, PhoneDateValueError) as e:
                    self._handle_known_error(e, instance, xforms)
                except Exception as e:
                    # handle / log the error and reraise so the phone knows to resubmit
                    # note that in the case of edit submissions this won't flag the previous
                    # submission as having been edited. this is intentional, since we should treat
                    # this use case as if the edit "failed"
                    handle_unexpected_error(self.interface, instance, e)
                    raise
                else:
                    instance.initial_processing_complete = True
                    self.save_processed_models(xforms, case_stock_result)
                    cases = case_stock_result.case_models

            errors = self.process_signals(instance)
            response = self._get_open_rosa_response(instance, errors)
            return response, instance, cases

    def save_processed_models(self, xforms, case_stock_result):
        from casexml.apps.case.signals import case_post_save
        instance = xforms[0]
        with unfinished_submission(instance) as unfinished_submission_stub:
            self.interface.save_processed_models(
                xforms,
                case_stock_result.case_models,
                case_stock_result.stock_result
            )

            unfinished_submission_stub.saved = True
            unfinished_submission_stub.save()

            case_stock_result.case_result.commit_dirtiness_flags()
            case_stock_result.stock_result.finalize()

            for case in case_stock_result.case_models:
                case_post_save.send(case.__class__, case=case)

        case_stock_result.case_result.close_extensions()

    def process_xforms_for_cases(self, xforms):
        from casexml.apps.case.xform import get_and_check_xform_domain
        from casexml.apps.case.xform import process_cases_with_casedb
        from corehq.apps.commtrack.processing import process_stock

        instance = xforms[0]

        domain = get_and_check_xform_domain(instance)
        with self.interface.casedb_cache(domain=domain, lock=True, deleted_ok=True, xforms=xforms) as case_db:
            case_result = process_cases_with_casedb(xforms, case_db)
            stock_result = process_stock(xforms, case_db)

            cases = case_db.get_cases_for_saving(instance.received_on)
            stock_result.populate_models()

        return CaseStockProcessingResult(
            case_result=case_result,
            case_models=cases,
            stock_result=stock_result,
        )

    def get_response(self):
        response, _, _ = self.run()
        return response

    def process_signals(self, instance):
        feedback = successful_form_received.send_robust(None, xform=instance)
        errors = []
        for func, resp in feedback:
            if resp and isinstance(resp, Exception):
                error_message = unicode(resp)
                logging.error((
                    u"Receiver app: problem sending "
                    u"post-save signal %s for xform %s: %s: %s"
                ) % (func, instance.form_id, type(resp).__name__, error_message))
                errors.append(error_message)
        if errors:
            self.interface.xformerror_from_xform_instance(instance, ", ".join(errors))
            self.formdb.update_form_problem_and_state(instance)
        return errors

    @staticmethod
    def get_failed_auth_response():
        return HttpResponseForbidden('Bad auth')

    def _get_open_rosa_response(self, instance, errors):
        if instance.is_normal:
            response = self.get_success_response(instance, errors)
        else:
            response = self.get_failure_response(instance)

        # this hack is required for ODK
        response["Location"] = self.location

        # this is a magic thing that we add
        response['X-CommCareHQ-FormID'] = instance.form_id
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
    def submission_ignored_response():
        return OpenRosaResponse(
            # would have done ✓ but our test Nokias' fonts don't have that character
            message=u'√ (this submission was ignored)',
            nature=ResponseNature.SUBMIT_SUCCESS,
            status=201,
        ).response()

    @staticmethod
    def get_failure_response(doc):
        return OpenRosaResponse(
            message=doc.problem,
            nature=ResponseNature.SUBMIT_ERROR,
            status=201,
        ).response()

    @staticmethod
    def get_exception_response_and_log(error_instance, path):
        logging.exception(
            u"Problem receiving submission to %s. Doc id: %s, Error %s" % (
                path,
                error_instance.form_id,
                error_instance.problem
            )
        )
        return OpenRosaResponse(
            message=("The sever got itself into big trouble! "
                     "Details: %s" % error_instance.problem),
            nature=ResponseNature.SUBMIT_ERROR,
            status=500,
        ).response()


def _transform_instance_to_error(interface, e, instance):
    error_message = '{}: {}'.format(
        type(e).__name__, unicode(e))
    logging.exception((
        u"Warning in case or stock processing "
        u"for form {}: {}."
    ).format(instance.form_id, error_message))
    return interface.xformerror_from_xform_instance(instance, error_message)


def handle_unexpected_error(interface, instance, e):
    # The following code saves the xform instance
    # as an XFormError, with a different ID.
    # That's because if you save with the original ID
    # and then resubmit, the new submission never has a
    # chance to get reprocessed; it'll just get saved as
    # a duplicate.
    _notify_submission_error(interface, instance, e)
    FormAccessors(interface.domain).save_new_form(instance)


def _notify_submission_error(interface, instance, e):
    from corehq.util.global_request.api import get_request
    request = get_request()
    error_message = u'{}: {}'.format(type(e).__name__, unicode(e))
    instance = interface.xformerror_from_xform_instance(instance, error_message, with_new_id=True)
    domain = getattr(instance, 'domain', '---')
    message = u"Error in case or stock processing for domain: {}".format(domain)
    details = {
        'original form ID': instance.orig_id,
        'error form ID': instance.form_id,
        'error message': error_message
    }
    should_email = not isinstance(e, CouchSaveAborted)  # intentionally don't double-email these
    if should_email:
        notify_exception(request, message, details=details)
    else:
        logging.error(message, exc_info=sys.exc_info(), extra={'details': details})


@contextlib.contextmanager
def unfinished_submission(instance):
    unfinished_submission_stub = UnfinishedSubmissionStub.objects.create(
        xform_id=instance.form_id,
        timestamp=datetime.datetime.utcnow(),
        saved=False,
        domain=instance.domain,
    )
    yield unfinished_submission_stub

    unfinished_submission_stub.delete()
