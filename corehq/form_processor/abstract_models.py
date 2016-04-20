import logging
from abc import ABCMeta, abstractmethod, abstractproperty

import six as six
from couchdbkit import ResourceNotFound

from dimagi.utils.decorators.memoized import memoized
from couchforms import const


class AbstractXFormInstance(object):

    # @property
    # def form_id(self):
    #     raise NotImplementedError()

    user_id = None

    @property
    def attachments(self):
        """
        Get the extra attachments for this form. This will not include
        the form itself
        """
        raise NotImplementedError

    @property
    def form_data(self):
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

    @property
    def is_deleted(self):
        raise NotImplementedError()

    # @property
    # def deletion_id(self):
    #     raise NotImplementedError

    def auth_context(self):
        raise NotImplementedError()

    def get_data(self, xpath):
        raise NotImplementedError()

    def get_attachment(self, attachment_name):
        raise NotImplementedError()

    def archive(self, user_id=None):
        raise NotImplementedError()

    def unarchive(self, user_id=None):
        raise NotImplementedError()

    def get_xml_element(self):
        raise NotImplementedError()

    def get_xml(self):
        raise NotImplementedError()

    def save(self, *args, **kwargs):
        raise NotImplementedError()

    def set_submission_properties(self, submission_post):
        raise NotImplementedError()

    def soft_delete(self):
        raise NotImplementedError()

    def to_json(self):
        raise NotImplementedError()

    @classmethod
    def get(self, xform_id):
        raise NotImplementedError()

    @property
    def xml_md5(self):
        raise NotImplementedError()

    @property
    def version(self):
        return self.form_data.get(const.TAG_VERSION, "")

    @property
    def uiversion(self):
        return self.form_data.get(const.TAG_UIVERSION, "")

    @property
    def type(self):
        return self.form_data.get(const.TAG_TYPE, "")

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

    # @property
    # def case_id(self):
    #     raise NotImplementedError()

    @property
    def case_name(self):
        raise NotImplementedError()

    @property
    def parent(self):
        raise NotImplementedError()

    def soft_delete(self):
        raise NotImplementedError()

    def get_attachment(self, attachment_name):
        raise NotImplementedError()

    def is_deleted(self):
        raise NotImplementedError()

    # @property
    # def deletion_id(self):
    #     raise NotImplementedError

    def dynamic_case_properties(self):
        raise NotImplementedError()

    def get_actions_for_form(self, xform):
        raise NotImplementedError

    def modified_since_sync(self, sync_log):
        raise NotImplementedError

    def get_subcases(self):
        raise NotImplementedError

    def get_case_property(self, property):
        raise NotImplementedError

    def to_json(self):
        raise NotImplementedError()

    def to_api_json(self):
        raise NotImplementedError()

    @memoized
    def get_index_map(self, reversed=False):
        return dict([
            (index.identifier, {
                "case_type": index.referenced_type,
                "case_id": index.referenced_id,
                "relationship": index.relationship,
            }) for index in (self.indices if not reversed else self.reverse_indices)
        ])

    def get_properties_in_api_format(self):
        return dict(self.dynamic_case_properties().items() + {
            "external_id": self.external_id,
            "owner_id": self.owner_id,
            # renamed
            "case_name": self.name,
            # renamed
            "case_type": self.type,
            # renamed
            "date_opened": self.opened_on,
            # all custom properties go here
        }.items())

    @memoized
    def get_attachment_map(self):
        return dict([
            (name, {
                'url': self.get_attachment_server_url(att.identifier),
                'mime': att.attachment_from
            }) for name, att in self.case_attachments.items()
        ])

    def to_xml(self, version, include_case_on_closed=False):
        from xml.etree import ElementTree
        from casexml.apps.phone.xml import get_case_element
        if self.closed:
            if include_case_on_closed:
                elem = get_case_element(self, ('create', 'update', 'close'), version)
            else:
                elem = get_case_element(self, ('close'), version)
        else:
            elem = get_case_element(self, ('create', 'update'), version)
        return ElementTree.tostring(elem)

    def get_attachment_server_url(self, identifier):
        """
        A server specific URL for remote clients to access case attachment resources async.
        """
        if identifier in self.case_attachments:
            from dimagi.utils import web
            from django.core.urlresolvers import reverse
            return "%s%s" % (web.get_url_base(),
                 reverse("api_case_attachment", kwargs={
                     "domain": self.domain,
                     "case_id": self.case_id,
                     "attachment_id": identifier,
                 })
            )
        else:
            return None


class AbstractSupplyInterface(six.with_metaclass(ABCMeta)):
    @classmethod
    @abstractmethod
    def get_by_location(cls, location):
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def get_or_create_by_location(cls, location):
        raise NotImplementedError


class IsImageMixin(object):
    @property
    def is_image(self):
        if self.content_type is None:
            return None
        return True if self.content_type.startswith('image/') else False


class CaseAttachmentMixin(IsImageMixin):
    @property
    def is_present(self):
        """
        Helper method to see if this is a delete vs. update
        """
        if self.identifier and (self.attachment_src == self.attachment_from is None):
            return False
        else:
            return True
