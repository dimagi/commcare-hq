import logging
from collections import namedtuple

from ddtrace import tracer
from django.db import IntegrityError
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _
import sys

from casexml.apps.case.xform import close_extension_cases
from casexml.apps.phone.restore_caching import AsyncRestoreTaskIdCache, RestorePayloadPathCache
import couchforms
from casexml.apps.case.exceptions import PhoneDateValueError, IllegalCaseId, UsesReferrals, InvalidCaseIndex, \
    CaseValueError
from corehq.apps.receiverwrapper.rate_limiter import report_case_usage, report_submission_usage
from corehq.const import OPENROSA_VERSION_3
from corehq.middleware import OPENROSA_VERSION_HEADER
from corehq.toggles import ASYNC_RESTORE, BLOCK_SUMOLOGIC_LOGS, NAMESPACE_OTHER, SUMOLOGIC_LOGS
from corehq.apps.app_manager.dbaccessors import get_current_app
from corehq.apps.cloudcare.const import DEVICE_ID as FORMPLAYER_DEVICE_ID
from corehq.apps.commtrack.exceptions import MissingProductId
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.apps.es.client import BulkActionItem
from corehq.apps.users.models import CouchUser
from corehq.apps.users.permissions import SUBMISSION_HISTORY_PERMISSION, has_permission_to_view_report
from corehq.form_processor.exceptions import PostSaveError, XFormSaveError
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.parsers.form import process_xform_xml
from corehq.form_processor.system_action import SYSTEM_ACTION_XMLNS, handle_system_action
from corehq.form_processor.utils.metadata import scrub_meta
from corehq.form_processor.submission_process_tracker import unfinished_submission
from corehq.util.metrics import metrics_counter
from corehq.util.metrics.load_counters import form_load_counter
from corehq.util.global_request import get_request
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext
from couchdbkit.exceptions import ResourceNotFound
from couchforms import openrosa_response
from couchforms.const import DEVICE_LOG_XMLNS
from couchforms.models import DefaultAuthContext, UnfinishedSubmissionStub
from couchforms.signals import successful_form_received
from couchforms.openrosa_response import OpenRosaResponse, ResponseNature
from dimagi.utils.logging import notify_exception, log_signal_errors
from phonelog.utils import process_device_log, SumoLogicLog


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
                 partial_submission=False, case_db=None, force_logs=False,
                 timing_context=None, instance_json=None):
        assert domain, "'domain' is required"
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
        self.instance_json = instance_json
        self.attachments = attachments or {}
        self.auth_context = auth_context or DefaultAuthContext()
        self.path = path
        self.interface = FormProcessorInterface(domain)
        self.partial_submission = partial_submission
        # always None except in the case where a system form is being processed as part of another submission
        # e.g. for closing extension cases
        self.case_db = case_db
        if case_db:
            assert case_db.domain == domain
        self.force_logs = force_logs

        self.is_openrosa_version3 = self.openrosa_headers.get(OPENROSA_VERSION_HEADER, '') == OPENROSA_VERSION_3
        self.track_load = form_load_counter("form_submission", domain)
        self.timing_context = timing_context or TimingContext()

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

    def _post_process_form(self, xform):
        self._set_submission_properties(xform)
        scrub_meta(xform)

    def _get_success_message(self, instance, cases=None):
        '''
        Formplayer requests get a detailed success message pointing to the form/case affected.
        All other requests get a generic message.

        Message is formatted with markdown.
        '''

        if instance.metadata and (not instance.metadata.userID or not instance.metadata.instanceID):
            metrics_counter('commcare.xform_submissions.partial_metadata', tags={
                'domain': instance.domain,
            })
        elif not instance.metadata:
            metrics_counter('commcare.xform_submissions.no_metadata', tags={
                'domain': instance.domain,
            })
            return '   √   '
        if instance.metadata.deviceID != FORMPLAYER_DEVICE_ID:
            return '   √   '

        user = CouchUser.get_by_user_id(instance.user_id)
        notification_text = self._get_form_submission_text(instance, user)
        if notification_text:
            messages = [notification_text]
        else:
            messages = [_("'{form_name}' successfully saved!")
                        .format(form_name=self._get_form_name(instance, user))]
        if user and user.is_web_user():
            messages.extend(self._success_message_links(user, instance, cases))
        return "\n\n".join(messages)

    def _get_form_name(self, instance, user):
        if instance.build_id:
            default_language, names_by_xmlns = _get_form_name_info(instance.domain, instance.build_id)
            names = names_by_xmlns.get(instance.xmlns, {})
            if user and user.language and names.get(user.language):
                return names[user.language]
            if names.get(default_language):
                return names[default_language]
        return instance.name

    def _get_form_submission_text(self, instance, user):
        if instance.build_id:
            default_language, submission_text_by_lang = _get_form_submit_notification_text_info(instance.domain,
                                                                                                instance.build_id)
            submission_text_dict = submission_text_by_lang.get(instance.xmlns, {})
            if user and user.language and submission_text_dict.get(user.language):
                return submission_text_dict[user.language]
            if submission_text_dict.get(default_language):
                return submission_text_dict[default_language]
        return None

    def _success_message_links(self, user, instance, cases):
        """Yield links to reports/exports, if accessible"""
        from corehq.apps.export.views.list import CaseExportListView, FormExportListView
        from corehq.apps.export.views.utils import can_view_case_exports, can_view_form_exports
        from corehq.apps.reports.standard.cases.case_data import CaseDataView
        from corehq.apps.reports.views import FormDataView
        form_link = case_link = form_export_link = case_export_link = None
        if has_permission_to_view_report(user, instance.domain, SUBMISSION_HISTORY_PERMISSION):
            form_link = reverse(FormDataView.urlname, args=[instance.domain, instance.form_id])
        case_view = 'corehq.apps.reports.standard.cases.basic.CaseListReport'
        if cases and has_permission_to_view_report(user, instance.domain, case_view):
            if len(cases) == 1:
                case_link = reverse(CaseDataView.urlname, args=[instance.domain, cases[0].case_id])
            else:
                case_link = ", ".join(["[{}]({})".format(
                    c.name, reverse(CaseDataView.urlname, args=[instance.domain, c.case_id])
                ) for c in cases])
        if can_view_form_exports(user, instance.domain):
            form_export_link = reverse(FormExportListView.urlname, args=[instance.domain])
        if cases and can_view_case_exports(user, instance.domain):
            case_export_link = reverse(CaseExportListView.urlname, args=[instance.domain])

        # Add link to form/case if possible
        if form_link and case_link:
            if len(cases) == 1:
                yield (_("You submitted [this form]({}), which affected [this case]({}).")
                       .format(form_link, case_link))
            else:
                yield (_("You submitted [this form]({}), which affected these cases: {}.")
                       .format(form_link, case_link))
        elif form_link:
            yield _("You submitted [this form]({}).").format(form_link)
        elif case_link:
            if len(cases) == 1:
                yield _("Your form affected [this case]({}).").format(case_link)
            else:
                yield _("Your form affected these cases: {}.").format(case_link)

        # Add link to all form/case exports
        if form_export_link and case_export_link:
            yield (_("Click to export your [case]({}) or [form]({}) data.")
                   .format(case_export_link, form_export_link))
        elif form_export_link:
            yield _("Click to export your [form data]({}).").format(form_export_link)
        elif case_export_link:
            yield _("Click to export your [case data]({}).").format(case_export_link)

    def run(self):
        self.track_load()
        with self.timing_context("process_xml"):
            report_submission_usage(self.domain)
            failure_response = self._handle_basic_failure_modes()
            if failure_response:
                return FormProcessingResult(failure_response, None, [], [], 'known_failures')

            result = process_xform_xml(
                self.domain,
                self.instance,
                self.attachments,
                self.auth_context.to_json(),
                instance_json=self.instance_json,
            )
            submitted_form = result.submitted_form

            self._post_process_form(submitted_form)
            self._invalidate_caches(submitted_form)

            if submitted_form.is_submission_error_log:
                logging.info('Processing form %s as a submission error', submitted_form.form_id)
                XFormInstance.objects.save_new_form(submitted_form)

                response = None
                try:
                    xml = self.instance.decode()
                except UnicodeDecodeError:
                    pass
                else:
                    if 'log_subreport' in xml:
                        response = self.get_exception_response_and_log(
                            'Badly formed device log', submitted_form, self.path
                        )

                if not response:
                    response = self.get_exception_response_and_log(
                        'Problem receiving submission', submitted_form, self.path
                    )
                return FormProcessingResult(response, None, [], [], 'submission_error_log')

        if submitted_form.xmlns == SYSTEM_ACTION_XMLNS:
            logging.info('Processing form %s as a system action', submitted_form.form_id)
            with self.timing_context("process_system_action"):
                return self.handle_system_action(submitted_form)

        if submitted_form.xmlns == DEVICE_LOG_XMLNS:
            logging.info('Processing form %s as a device log', submitted_form.form_id)
            with self.timing_context("process_device_log"):
                return self.process_device_log(submitted_form)

        # Begin Normal Form Processing
        self._log_form_details(submitted_form)

        cases = []
        ledgers = []
        submission_type = 'unknown'
        openrosa_kwargs = {}
        with result.get_locked_forms() as xforms:
            if len(xforms) > 1:
                self.track_load(len(xforms) - 1)
            if self.case_db:
                case_db_cache = self.case_db
                case_db_cache.cached_xforms.extend(xforms)
            else:
                case_db_cache = self.interface.casedb_cache(
                    domain=self.domain, lock=True, deleted_ok=True,
                    xforms=xforms, load_src="form_submission",
                )

            with case_db_cache as case_db:
                instance = xforms[0]

                if instance.is_duplicate:
                    with self.timing_context("process_duplicate"), tracer.trace('submission.process_duplicate'):
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
                            openrosa_kwargs['error_message'] = result.error
                            if existing_form.is_error:
                                openrosa_kwargs['error_nature'] = ResponseNature.PROCESSING_FAILURE
                            else:
                                openrosa_kwargs['error_nature'] = ResponseNature.POST_PROCESSING_FAILURE
                        else:
                            self.interface.save_processed_models([instance])
                elif not instance.is_error:
                    submission_type = 'normal'
                    try:
                        case_stock_result = self.process_xforms_for_cases(xforms, case_db, self.timing_context)
                    except (IllegalCaseId, UsesReferrals, MissingProductId,
                            PhoneDateValueError, InvalidCaseIndex, CaseValueError) as e:
                        self._handle_known_error(e, instance, xforms)
                        submission_type = 'error'
                        openrosa_kwargs['error_nature'] = ResponseNature.PROCESSING_FAILURE
                    except Exception as e:
                        # handle / log the error and reraise so the phone knows to resubmit
                        # note that in the case of edit submissions this won't flag the previous
                        # submission as having been edited. this is intentional, since we should treat
                        # this use case as if the edit "failed"
                        handle_unexpected_error(self.interface, instance, e)
                        raise
                    else:
                        instance.initial_processing_complete = True
                        report_case_usage(self.domain, len(case_stock_result.case_models))
                        openrosa_kwargs['error_message'] = self.save_processed_models(case_db, xforms,
                                                                                      case_stock_result)
                        if openrosa_kwargs['error_message']:
                            openrosa_kwargs['error_nature'] = ResponseNature.POST_PROCESSING_FAILURE
                        cases = case_stock_result.case_models
                        ledgers = case_stock_result.stock_result.models_to_save
                        openrosa_kwargs['success_message'] = self._get_success_message(instance, cases=cases)
                elif instance.is_error:
                    submission_type = 'error'

            self._log_form_completion(instance, submission_type)

            response = self._get_open_rosa_response(instance, **openrosa_kwargs)
            return FormProcessingResult(response, instance, cases, ledgers, submission_type)

    def _log_form_details(self, form):
        attachments = form.attachments if hasattr(form, 'attachments') else {}

        logging.info('Received Form %s with %d attachments',
            form.form_id, len(attachments))

        for index, (name, attachment) in enumerate(attachments.items()):
            attachment_msg = 'Form %s, Attachment %s: %s'
            attachment_props = [form.form_id, index, name]

            if hasattr(attachment, 'has_size') and attachment.has_size():
                attachment_msg = attachment_msg + ' (%d bytes)'
                attachment_props.append(attachment.raw_content.size)

            logging.info(attachment_msg, *attachment_props)

    def _log_form_completion(self, form, submission_type):
        # Orig_id doesn't exist on all couch forms, only XFormError and XFormDeprecated
        if hasattr(form, 'orig_id') and form.orig_id is not None:
            logging.info('Finished %s processing for Form %s with original id %s',
                submission_type, form.form_id, form.orig_id)
        else:
            logging.info('Finished %s processing for Form %s', submission_type, form.form_id)

    def _conditionally_send_device_logs_to_sumologic(self, instance):
        url = getattr(settings, 'SUMOLOGIC_URL', None)
        if (url and SUMOLOGIC_LOGS.enabled(instance.form_data.get('device_id'), NAMESPACE_OTHER)
                and not BLOCK_SUMOLOGIC_LOGS.enabled(self.domain)):
            SumoLogicLog(self.domain, instance).send_data(url)

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
            from corehq.apps.celery import app
            app.control.revoke(task_id)
            async_restore_task_id_cache.invalidate()

    @tracer.wrap(name='submission.save_models')
    def save_processed_models(self, case_db, xforms, case_stock_result):
        instance = xforms[0]
        try:
            with self.timing_context("save_models"), unfinished_submission(instance) as unfinished_submission_stub:
                try:
                    self.interface.save_processed_models(
                        xforms,
                        case_stock_result.case_models,
                        case_stock_result.stock_result
                    )
                except PostSaveError:
                    # mark the stub as saved if there's a post save error
                    # but re-raise the error so that the re-processing queue picks it up
                    unfinished_submission_stub.submission_saved()
                    raise
                else:
                    unfinished_submission_stub.submission_saved()

                with self.timing_context("post_save_actions"):
                    self.do_post_save_actions(case_db, xforms, case_stock_result)
        except PostSaveError:
            return "Error performing post save operations"

    @staticmethod
    @tracer.wrap(name='submission.post_save_actions')
    def do_post_save_actions(case_db, xforms, case_stock_result):
        instance = xforms[0]
        case_db.clear_changed()
        try:
            case_stock_result.stock_result.finalize()

            SubmissionPost.index_case_search(instance, case_stock_result.case_models)

            SubmissionPost._fire_post_save_signals(instance, case_stock_result.case_models)

            close_extension_cases(
                case_db,
                case_stock_result.case_models,
                "SubmissionPost-%s-close_extensions" % instance.form_id,
                instance.last_sync_token
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
    def index_case_search(instance, case_models):
        if not instance.metadata or instance.metadata.deviceID != FORMPLAYER_DEVICE_ID:
            return

        from corehq.apps.case_search.models import case_search_synchronous_web_apps_for_domain
        if not case_search_synchronous_web_apps_for_domain(instance.domain):
            return

        from corehq.apps.es.case_search import case_search_adapter
        actions = [
            BulkActionItem.index(case_model)
            for case_model in case_models
        ]
        try:
            _, errors = case_search_adapter.bulk(actions, raise_errors=False, refresh=True)
        except Exception as e:
            errors = [str(e)]

        if errors:
            # Notify but otherwise ignore all errors - the regular case search pillow is going to reprocess these
            notify_exception(None, "Error updating case_search ES index during form processing", details={
                'xml': instance,
                'domain': instance.domain,
                'errors': errors,
            })

    @staticmethod
    @tracer.wrap(name='submission.process_cases_and_stock')
    def process_xforms_for_cases(xforms, case_db, timing_context=None):
        from casexml.apps.case.xform import process_cases_with_casedb
        from corehq.apps.commtrack.processing import process_stock

        timing_context = timing_context or TimingContext()

        instance = xforms[0]

        with timing_context("process_cases"):
            case_result = process_cases_with_casedb(xforms, case_db)
        with timing_context("process_ledgers"):
            stock_result = process_stock(xforms, case_db)
            stock_result.populate_models()

        modified_on_date = instance.received_on
        if getattr(instance, 'edited_on', None) and instance.edited_on > instance.received_on:
            modified_on_date = instance.edited_on

        with timing_context("check_cases_before_save"):
            cases = case_db.get_cases_for_saving(modified_on_date)

        return CaseStockProcessingResult(
            case_result=case_result,
            case_models=cases,
            stock_result=stock_result,
        )

    def get_response(self):
        return self.run().response

    @staticmethod
    def _fire_post_save_signals(instance, cases):
        from corehq.form_processor.signals import sql_case_post_save
        error_message = "Error occurred during form submission post save (%s)"
        error_details = {'domain': instance.domain, 'form_id': instance.form_id}
        results = successful_form_received.send_robust(None, xform=instance)
        has_errors = log_signal_errors(results, error_message, error_details)

        for case in cases:
            results = sql_case_post_save.send_robust(case.__class__, case=case)
            has_errors |= log_signal_errors(results, error_message, error_details)
        if has_errors:
            raise PostSaveError

    def _get_open_rosa_response(self, instance, success_message=None, error_message=None, error_nature=None):
        if self.is_openrosa_version3:
            instance_ok = instance.is_normal or instance.is_duplicate
            has_error = error_message or error_nature
            if instance_ok and not has_error:
                response = openrosa_response.get_openarosa_success_response(message=success_message)
            else:
                error_message = error_message or instance.problem
                response = self.get_v3_error_response(error_message, error_nature)
        else:
            if instance.is_normal:
                response = openrosa_response.get_openarosa_success_response()
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
    def get_v3_error_response(message, nature):
        """Returns a 422(Unprocessable Entity) response
        - if nature == 'processing_failure' the mobile device will quarantine this form and not retry it
        - any other value of `nature` will result in the form being marked as a failure and retrying
        """
        return OpenRosaResponse(
            message=message, nature=nature, status=422,
        ).response()

    @staticmethod
    def get_exception_response_and_log(msg, error_instance, path):
        logging.warning(
            msg,
            extra={
                'submission_path': path,
                'form_id': error_instance.form_id,
                'error_message': error_instance.problem
            }
        )
        # This are generally badly formed XML resulting from file corruption, encryption errors
        # or other errors on the device which can not be recovered from.
        # To prevent retries of these errors we submit a 422 response with `processing_failure` nature.
        return OpenRosaResponse(
            message="There was an error processing the form: %s" % error_instance.problem,
            nature=ResponseNature.PROCESSING_FAILURE,
            status=422,
        ).response()

    @tracer.wrap(name='submission.handle_system_action')
    def handle_system_action(self, form):
        handle_system_action(form, self.auth_context)
        self.interface.save_processed_models([form])
        response = HttpResponse(status=201)
        return FormProcessingResult(response, form, [], [], 'system-action')

    @tracer.wrap(name='submission.process_device_log')
    def process_device_log(self, device_log_form):
        self._conditionally_send_device_logs_to_sumologic(device_log_form)
        ignore_device_logs = settings.SERVER_ENVIRONMENT in settings.NO_DEVICE_LOG_ENVS
        if self.force_logs or not ignore_device_logs:
            try:
                process_device_log(self.domain, device_log_form, self.force_logs)
            except Exception as e:
                notify_exception(None, "Error processing device log", details={
                    'xml': self.instance,
                    'domain': self.domain
                })
                e.sentry_capture = False
                raise

        response = self._get_open_rosa_response(device_log_form)
        return FormProcessingResult(response, device_log_form, [], [], 'device-log')


def _transform_instance_to_error(interface, exception, instance):
    error_message = '{}: {}'.format(type(exception).__name__, str(exception))
    return interface.xformerror_from_xform_instance(instance, error_message)


def handle_unexpected_error(interface, instance, exception):
    instance = _transform_instance_to_error(interface, exception, instance)

    notify_submission_error(instance, instance.problem, sys.exc_info())

    try:
        XFormInstance.objects.save_new_form(instance)
    except IntegrityError:
        # handle edge case where saving duplicate form fails
        instance = interface.xformerror_from_xform_instance(instance, instance.problem, with_new_id=True)
        XFormInstance.objects.save_new_form(instance)
    except XFormSaveError:
        # try a simple save
        instance.save()


def notify_submission_error(instance, message, exec_info=None):
    from corehq.util.global_request.api import get_request

    exec_info = exec_info or sys.exc_info()
    domain = getattr(instance, 'domain', '---')
    details = {
        'domain': domain,
        'error form ID': instance.form_id,
    }
    request = get_request()
    notify_exception(request, message, details=details, exec_info=exec_info)


@quickcache(['domain', 'build_id'])
def _get_form_name_info(domain, build_id):
    """
    :return: (default_language, {'http://my.xmlns': {'en': 'My Form'}})
    """
    try:
        app_build = get_current_app(domain, build_id)
    except ResourceNotFound:
        return 'en', {}
    return (
        app_build.default_language,
        {form.xmlns: dict(form.name) for form in app_build.get_forms() if form.form_type != 'shadow_form'}
    )


@quickcache(['domain', 'build_id'])
def _get_form_submit_notification_text_info(domain, build_id):
    try:
        app_build = get_current_app(domain, build_id)
    except ResourceNotFound:
        return 'en', {}
    return (
        app_build.default_language,
        {form.xmlns: dict(form.submit_notification_label) for form in app_build.get_forms()}
    )
