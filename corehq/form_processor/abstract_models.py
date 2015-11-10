import logging
from couchdbkit import ResourceNotFound
from dimagi.utils.decorators.memoized import memoized


class AbstractXFormInstance(object):

    @property
    def form_id(self):
        raise NotImplementedError()

    def auth_context(self):
        raise NotImplementedError()

    @property
    def form_data(self):
        raise NotImplementedError()

    def get_data(self, xpath):
        raise NotImplementedError()

    def get_attachment(self, attachment_name):
        raise NotImplementedError()

    def archive(self, user=None):
        raise NotImplementedError()

    def unarchive(self, user=None):
        raise NotImplementedError()

    def get_xml_element(self):
        raise NotImplementedError()

    def get_xml(self):
        raise NotImplementedError()

    @classmethod
    def get(self, xform_id):
        raise NotImplementedError()

    @classmethod
    def get_with_attachments(slef, xform_id):
        raise NotImplementedError()

    def save(self, *args, **kwargs):
        raise NotImplementedError()

    def set_submission_properties(self, submission_post):
        raise NotImplementedError()

    def to_json(self):
        raise NotImplementedError()

    @property
    def metadata(self):
        raise NotImplementedError()

    @property
    def is_normal(self):
        raise NotImplementedError()

    @property
    def is_archived(self):
        raise NotImplementedError()

    @property
    def is_deprecated(self):
        raise NotImplementedError()

    @property
    def is_duplicate(self):
        raise NotImplementedError()

    @property
    def is_error(self):
        raise NotImplementedError()

    @property
    def is_submission_error_log(self):
        raise NotImplementedError()

    @memoized
    def get_sync_token(self):
        from casexml.apps.phone.models import get_properly_wrapped_sync_log
        if self.last_sync_token:
            try:
                return get_properly_wrapped_sync_log(self.last_sync_token)
            except ResourceNotFound:
                logging.exception('No sync token with ID {} found. Form is {} in domain {}'.format(
                    self.last_sync_token, self.form_id, self.domain,
                ))
                raise
        return None


class AbstractCommCareCase(object):

    @property
    def case_id(self):
        raise NotImplementedError()

    @property
    def case_name(self):
        raise NotImplementedError()

    def hard_delete(self):
        raise NotImplementedError()

    def soft_delete(self):
        raise NotImplementedError()

    def get_attachment(self, attachment_name):
        raise NotImplementedError()

    def is_deleted(self):
        raise NotImplementedError()

    def to_xml(self, version, include_case_on_closed=False):
        raise NotImplementedError()

    def dynamic_case_properties(self):
        raise NotImplementedError()

    @classmethod
    def get(cls, case_id):
        raise NotImplementedError()

    @classmethod
    def get_cases(cls, ids):
        raise NotImplementedError()

    @classmethod
    def get_case_xform_ids(cls, case_id):
        raise NotImplementedError()
