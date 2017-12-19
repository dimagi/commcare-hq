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
from django.conf import settings
import sys
from casexml.apps.phone.restore_caching import AsyncRestoreTaskIdCache, RestorePayloadPathCache
import couchforms
from casexml.apps.case.exceptions import PhoneDateValueError, IllegalCaseId, UsesReferrals, InvalidCaseIndex, \
    CaseValueError
from corehq.const import OPENROSA_VERSION_3
from corehq.middleware import OPENROSA_VERSION_HEADER
from corehq.toggles import ASYNC_RESTORE
from corehq.apps.commtrack.exceptions import MissingProductId
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.form_processor.exceptions import CouchSaveAborted, PostSaveError
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.parsers.form import process_xform_xml
from corehq.form_processor.utils.metadata import scrub_meta
from corehq.util.global_request import get_request
from couchforms import openrosa_response
from couchforms.const import BadRequest, DEVICE_LOG_XMLNS
from couchforms.models import DefaultAuthContext, UnfinishedSubmissionStub
from couchforms.signals import successful_form_received
from couchforms.util import legacy_notification_assert
from couchforms.openrosa_response import OpenRosaResponse, ResponseNature
from dimagi.utils.logging import notify_exception, log_signal_errors
from phonelog.utils import process_device_log

from celery.task.control import revoke as revoke_celery_task
import six

CaseStockProcessingResult = namedtuple(
    'CaseStockProcessingResult',
    'case_result, case_models, stock_result'
)


class FormProcessingResult(namedtuple('FormProcessingResult', 'response xform cases ledgers submission_type')):
    @property
    def case(self):
        assert len(self.cases) == 1
        return self.cases[0]


class SubmissionPost(object):

    def __init__(self, instance=None, attachments=None, auth_context=None,
                 domain=None, app_id=None, build_id=None, path=None,
                 location=None, submit_ip=None, openrosa_headers=None,
                 last_sync_token=None, received_on=None, date_header=None,
                 partial_submission=False, case_db=None):
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
        # always None except in the case where a system form is being processed as part of another submission
        # e.g. for closing extension cases
        self.case_db = case_db

        self.is_openrosa_version3 = self.openrosa_headers.get(OPENROSA_VERSION_HEADER, '') == OPENROSA_VERSION_3

    def _set_submission_properties(self, xform):
        # attaches shared properties of the request to the document.
        # used on forms and errors
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
        xforms[0] = _transform_instance_to_error(self.interface, error, instance)
        # this is usually just one document, but if an edit errored we want
        # to save the deprecated form as well
        self.interface.save_processed_models(xforms)

    def _handle_basic_failure_modes(self):
        if any_migrations_in_progress(self.domain):
            # keep submissions on the phone
            # until ready to start accepting again
            return HttpResponse(status=503)

        if not self.auth_context.is_valid():
            return HttpResponseForbidden('Bad auth')

        if isinstance(self.instance, BadRequest):
            return HttpResponseBadRequest(self.instance.message)

    def _post_process_form(self, xform):
        self._set_submission_properties(xform)
        found_old = scrub_meta(xform)
        legacy_notification_assert(not found_old, 'Form with old metadata submitted', xform.form_id)

    def run(self):
        failure_response = self._handle_basic_failure_modes()
        if failure_response:
            return FormProcessingResult(failure_response, None, [], [], 'known_failures')

        result = process_xform_xml(self.domain, self.instance, self.attachments, self.auth_context.to_json())
        submitted_form = result.submitted_form

        self._post_process_form(submitted_form)
        self._invalidate_caches(submitted_form)
        submission_type = None

        if submitted_form.is_submission_error_log:
            self.formdb.save_new_form(submitted_form)
            response = self.get_exception_response_and_log(submitted_form, self.path)
            return FormProcessingResult(response, None, [], [], 'submission_error_log')

        cases = []
        ledgers = []
        submission_type = 'unknown'
        response_nature = error_message = None
        with result.get_locked_forms() as xforms:
            from casexml.apps.case.xform import get_and_check_xform_domain
            domain = get_and_check_xform_domain(xforms[0])
            if self.case_db:
                assert self.case_db.domain == domain
                case_db_cache = self.case_db
                case_db_cache.cached_xforms.extend(xforms)
            else:
                case_db_cache = self.interface.casedb_cache(domain=domain, lock=True, deleted_ok=True, xforms=xforms)

            with case_db_cache as case_db:
                instance = xforms[0]
                # ignore temporarily till we migrate DeviceReportEntry id to bigint
                ignore_device_logs = settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS
                if not ignore_device_logs and instance.xmlns == DEVICE_LOG_XMLNS:
                    submission_type = 'device_log'
                    try:
                        process_device_log(self.domain, instance)
                    except Exception:
                        notify_exception(None, "Error processing device log", details={
                            'xml': self.instance,
                            'domain': self.domain
                        })
                        raise

                elif instance.is_duplicate:
                    submission_type = 'duplicate'
                    existing_form = xforms[1]
                    stub = UnfinishedSubmissionStub.objects.filter(
                        domain=instance.domain,
                        xform_id=existing_form.form_id
                    ).first()

                    result = None
                    if stub:
                        from corehq.form_processor.reprocess import reprocess_unfinished_stub_with_form
                        result = reprocess_unfinished_stub_with_form(stub, existing_form, lock=False)
                    elif existing_form.is_error:
                        from corehq.form_processor.reprocess import reprocess_form
                        result = reprocess_form(existing_form, lock_form=False)
                    if result and result.error:
                        submission_type = 'error'
                        error_message = result.error
                        if existing_form.is_error:
                            response_nature = ResponseNature.PROCESSING_FAILURE
                        else:
                            response_nature = ResponseNature.POST_PROCESSING_FAILURE
                    else:
                        self.interface.save_processed_models([instance])
                elif not instance.is_error:
                    submission_type = 'normal'
                    try:
                        case_stock_result = self.process_xforms_for_cases(xforms, case_db)
                    except (IllegalCaseId, UsesReferrals, MissingProductId,
                            PhoneDateValueError, InvalidCaseIndex, CaseValueError) as e:
                        self._handle_known_error(e, instance, xforms)
                        submission_type = 'error'
                        response_nature = ResponseNature.PROCESSING_FAILURE
                    except Exception as e:
                        # handle / log the error and reraise so the phone knows to resubmit
                        # note that in the case of edit submissions this won't flag the previous
                        # submission as having been edited. this is intentional, since we should treat
                        # this use case as if the edit "failed"
                        handle_unexpected_error(self.interface, instance, e)
                        raise
                    else:
                        instance.initial_processing_complete = True
                        error_message = self.save_processed_models(case_db, xforms, case_stock_result)
                        if error_message:
                            response_nature = ResponseNature.POST_PROCESSING_FAILURE
                        cases = case_stock_result.case_models
                        ledgers = case_stock_result.stock_result.models_to_save
                elif instance.is_error:
                    submission_type = 'error'

            response = self._get_open_rosa_response(instance, error_message, response_nature)
            return FormProcessingResult(response, instance, cases, ledgers, submission_type)

    def _invalidate_caches(self, xform):
        for device_id in {None, xform.metadata.deviceID if xform.metadata else None}:
            self._invalidate_restore_payload_path_cache(xform, device_id)
            if ASYNC_RESTORE.enabled(self.domain):
                self._invalidate_async_restore_task_id_cache(xform, device_id)

    def _invalidate_restore_payload_path_cache(self, xform, device_id):
        """invalidate cached initial restores"""
        restore_payload_path_cache = RestorePayloadPathCache(
            domain=self.domain,
            user_id=xform.user_id,
            sync_log_id=xform.last_sync_token,
            device_id=device_id,
        )
        restore_payload_path_cache.invalidate()

    def _invalidate_async_restore_task_id_cache(self, xform, device_id):
        async_restore_task_id_cache = AsyncRestoreTaskIdCache(
            domain=self.domain,
            user_id=xform.user_id,
            sync_log_id=self.last_sync_token,
            device_id=device_id,
        )

        task_id = async_restore_task_id_cache.get_value()

        if task_id is not None:
            revoke_celery_task(task_id)
            async_restore_task_id_cache.invalidate()

    def save_processed_models(self, case_db, xforms, case_stock_result):
        instance = xforms[0]
        try:
            with unfinished_submission(instance) as unfinished_submission_stub:
                self.interface.save_processed_models(
                    xforms,
                    case_stock_result.case_models,
                    case_stock_result.stock_result
                )

                if unfinished_submission_stub:
                    unfinished_submission_stub.saved = True
                    unfinished_submission_stub.save()

                self.do_post_save_actions(case_db, xforms, case_stock_result)
        except PostSaveError:
            return "Error performing post save operations"

    @staticmethod
    def do_post_save_actions(case_db, xforms, case_stock_result):
        instance = xforms[0]
        try:
            case_stock_result.case_result.commit_dirtiness_flags()
            case_stock_result.stock_result.finalize()

            SubmissionPost._fire_post_save_signals(instance, case_stock_result.case_models)

            case_stock_result.case_result.close_extensions(
                case_db,
                "SubmissionPost-%s-close_extensions" % instance.form_id
            )
        except PostSaveError:
            raise
        except Exception:
            notify_exception(get_request(), "Error performing post save actions during form processing", {
                'domain': instance.domain,
                'form_id': instance.form_id,
            })
            raise PostSaveError

    @staticmethod
    def process_xforms_for_cases(xforms, case_db):
        from casexml.apps.case.xform import process_cases_with_casedb
        from corehq.apps.commtrack.processing import process_stock

        instance = xforms[0]

        case_result = process_cases_with_casedb(xforms, case_db)
        stock_result = process_stock(xforms, case_db)

        modified_on_date = instance.received_on
        if getattr(instance, 'edited_on', None) and instance.edited_on > instance.received_on:
            modified_on_date = instance.edited_on
        cases = case_db.get_cases_for_saving(modified_on_date)
        stock_result.populate_models()

        return CaseStockProcessingResult(
            case_result=case_result,
            case_models=cases,
            stock_result=stock_result,
        )

    def get_response(self):
        return self.run().response

    @staticmethod
    def _fire_post_save_signals(instance, cases):
        from casexml.apps.case.signals import case_post_save
        error_message = "Error occurred during form submission post save (%s)"
        error_details = {'domain': instance.domain, 'form_id': instance.form_id}
        results = successful_form_received.send_robust(None, xform=instance)
        has_errors = log_signal_errors(results, error_message, error_details)

        for case in cases:
            results = case_post_save.send_robust(case.__class__, case=case)
            has_errors |= log_signal_errors(results, error_message, error_details)
        if has_errors:
            raise PostSaveError

    def _get_open_rosa_response(self, instance, error_message=None, error_nature=None):
        if self.is_openrosa_version3:
            instance_ok = instance.is_normal or instance.is_duplicate
            has_error = error_message or error_nature
            if instance_ok and not has_error:
                response = openrosa_response.SUCCESS_RESPONSE
            else:
                error_message = error_message or instance.problem
                response = self.get_retry_response(error_message, error_nature)
        else:
            if instance.is_normal:
                response = openrosa_response.SUCCESS_RESPONSE
            else:
                response = self.get_v2_submit_error_response(instance)

        # this hack is required for ODK
        response["Location"] = self.location

        # this is a magic thing that we add
        response['X-CommCareHQ-FormID'] = instance.form_id
        return response

    @staticmethod
    def get_v2_submit_error_response(doc):
        return OpenRosaResponse(
            message=doc.problem, nature=ResponseNature.SUBMIT_ERROR, status=201,
        ).response()

    @staticmethod
    def get_retry_response(message, nature):
        """Returns a 422(Unprocessable Entity) response, mobile will retry this submission
        """
        return OpenRosaResponse(
            message=message, nature=nature, status=422,
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
            message="There was an error processing the form: %s" % error_instance.problem,
            nature=ResponseNature.SUBMIT_ERROR,
            status=500,
        ).response()


def _transform_instance_to_error(interface, exception, instance):
    error_message = u'{}: {}'.format(type(exception).__name__, six.text_type(exception))
    return interface.xformerror_from_xform_instance(instance, error_message)


def handle_unexpected_error(interface, instance, exception, message=None):
    instance = _transform_instance_to_error(interface, exception, instance)
    _notify_submission_error(instance, exception, instance.problem)
    FormAccessors(interface.domain).save_new_form(instance)


def _notify_submission_error(instance, exception, message):
    from corehq.util.global_request.api import get_request
    domain = getattr(instance, 'domain', '---')
    details = {
        'domain': domain,
        'error form ID': instance.form_id,
    }
    should_email = not isinstance(exception, CouchSaveAborted)  # intentionally don't double-email these
    if should_email:
        request = get_request()
        notify_exception(request, message, details=details)
    else:
        logging.error(message, exc_info=sys.exc_info(), extra={'details': details})


@contextlib.contextmanager
def unfinished_submission(instance):
    unfinished_submission_stub = None
    if not getattr(instance, 'deprecated_form_id', None):
        # don't create stubs for form edits since we don't want to auto-reprocess them
        unfinished_submission_stub = UnfinishedSubmissionStub.objects.create(
            xform_id=instance.form_id,
            timestamp=datetime.datetime.utcnow(),
            saved=False,
            domain=instance.domain,
        )
    yield unfinished_submission_stub

    if unfinished_submission_stub:
        unfinished_submission_stub.delete()
