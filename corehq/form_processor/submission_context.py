import lxml.etree
from memoized import memoized
import xml2json

from corehq import toggles
from corehq.form_processor.extension_points import get_form_submission_context_class
from corehq.form_processor.utils.metadata import scrub_meta

from casexml.apps.phone.restore_caching import AsyncRestoreTaskIdCache, RestorePayloadPathCache
from couchforms.util import legacy_notification_assert

from celery.task.control import revoke as revoke_celery_task


class SubmissionFormContext(object):
    def __init__(self, domain, instance, submit_ip, path, openrosa_headers, last_sync_token, received_on,
                 date_header, app_id, build_id, partial_submission):
        self.domain = domain
        self._instance = instance
        self.submit_ip = submit_ip
        self.path = path
        self.openrosa_headers = openrosa_headers
        self.last_sync_token = last_sync_token
        self.received_on = received_on
        self.date_header = date_header
        self.app_id = app_id
        self.build_id = build_id
        self.partial_submission = partial_submission

    def get_instance_xml(self):
        try:
            return xml2json.get_xml_from_string(self._instance)
        except xml2json.XMLSyntaxError:
            return None

    def get_instance(self):
        return self._instance

    def update_instance(self, xml):
        self._instance = lxml.etree.tostring(xml)

    def pre_process_form(self):
        # over write this method to add pre processing to form
        pass

    def post_process_form(self, xform):
        self.set_submission_properties(xform)
        found_old = scrub_meta(xform)
        legacy_notification_assert(not found_old, 'Form with old metadata submitted', xform.form_id)
        self.invalidate_caches(xform)

    def set_submission_properties(self, xform):
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

    def invalidate_caches(self, xform):
        for device_id in {None, xform.metadata.deviceID if xform.metadata else None}:
            self._invalidate_restore_payload_path_cache(xform, device_id)
            if toggles.ASYNC_RESTORE.enabled(self.domain):
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


@memoized
def form_submission_context_class():
    return get_form_submission_context_class() or SubmissionFormContext
