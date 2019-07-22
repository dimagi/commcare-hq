from __future__ import absolute_import
from __future__ import unicode_literals
import collections
import logging
from abc import ABCMeta, abstractmethod

import six as six

from casexml.apps.phone.exceptions import MissingSyncLog

from memoized import memoized
from couchforms import const


DEFAULT_PARENT_IDENTIFIER = 'parent'


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

    def archive(self, user_id=None, trigger_signals=True):
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

    def set_meta_properties(self):
        # noop - applicable for only SQL model
        pass

    @classmethod
    def get(self, xform_id):
        raise NotImplementedError()

    @property
    def xml_md5(self):
        raise NotImplementedError()

    @property
    def type(self):
        return self.form_data.get(const.TAG_TYPE, "")

    @property
    def name(self):
        return self.form_data.get(const.TAG_NAME, "")

    @memoized
    def get_sync_token(self):
        from casexml.apps.phone.models import get_properly_wrapped_sync_log
        if self.last_sync_token:
            try:
                return get_properly_wrapped_sync_log(self.last_sync_token)
            except MissingSyncLog:
                pass
        return None


def get_index_map(indices):
    return dict([
        (index.identifier, {
            "case_type": index.referenced_type,
            "case_id": index.referenced_id,
            "relationship": index.relationship,
        }) for index in indices
    ])


class CaseToXMLMixin(object):
    def to_xml(self, version, include_case_on_closed=False):
        from xml.etree import cElementTree as ElementTree
        from casexml.apps.phone.xml import get_case_element
        if self.closed:
            if include_case_on_closed:
                elem = get_case_element(self, ('create', 'update', 'close'), version)
            else:
                elem = get_case_element(self, ('close'), version)
        else:
            elem = get_case_element(self, ('create', 'update'), version)
        return ElementTree.tostring(elem)


class AbstractCommCareCase(CaseToXMLMixin):

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

    def get_subcases(self, index_identifier=None):
        raise NotImplementedError

    def get_parent(self, identifier=None, relationship=None):
        raise NotImplementedError

    def get_case_property(self, property):
        raise NotImplementedError

    def get_closing_transactions(self):
        raise NotImplementedError

    def get_opening_transactions(self):
        raise NotImplementedError

    def to_json(self):
        raise NotImplementedError()

    def to_api_json(self):
        raise NotImplementedError()

    def set_case_id(self, case_id):
        raise NotImplementedError()

    def _resolve_case_property(self, property_name, result):
        CasePropertyResult = collections.namedtuple('CasePropertyResult', 'case value')

        if property_name.lower().startswith('parent/'):
            parents = self.get_parent(identifier=DEFAULT_PARENT_IDENTIFIER)
            for parent in parents:
                parent._resolve_case_property(property_name[7:], result)
            return

        if property_name.lower().startswith('host/'):
            host = self.host
            if host:
                host._resolve_case_property(property_name[5:], result)
            return

        from corehq.form_processor.models import CommCareCaseSQL
        if isinstance(self, CommCareCaseSQL):
            if property_name == '_id':
                property_name = 'case_id'

            # Use .get_case_property() for the CommCareCaseSQL because
            # using .to_json() makes a lot of unnecessary db calls to find
            # things like case indices and case actions which we don't need here
            result.append(CasePropertyResult(
                self,
                self.get_case_property(property_name)
            ))
        else:
            # Use .to_json() for the couch CommCareCase because if we used
            # get_case_property() then dynamic case properties might end
            # up being coerced into data types other than string
            result.append(CasePropertyResult(
                self,
                self.to_json().get(property_name)
            ))

    def resolve_case_property(self, property_name):
        """
        Takes a case property expression and resolves the necessary references
        to get the case property value(s).

        property_name - The case property expression. Examples: name, parent/name,
                        parent/parent/name

        Returns a list of named tuples of (case, value), where value is the
        resolved case property value and case is the case that yielded that value.
        There can be more than one tuple in the returned result if a case has more
        than one parent or grandparent.
        """
        result = []
        self._resolve_case_property(property_name, result)
        return result

    @memoized
    def get_index_map(self, reversed=False):
        indices = self.indices if not reversed else self.reverse_indices
        return get_index_map(indices)

    def get_properties_in_api_format(self):
        return dict(list(self.dynamic_case_properties().items()) + list({
            "external_id": self.external_id,
            "owner_id": self.owner_id,
            # renamed
            "case_name": self.name,
            # renamed
            "case_type": self.type,
            # renamed
            "date_opened": self.opened_on,
            # all custom properties go here
        }.items()))

    @memoized
    def get_attachment_map(self):
        return {
            name: {
                'url': self.get_attachment_server_url(att.identifier),
                'content_type': att.content_type,
            }
            for name, att in self.case_attachments.items()
        }

    def to_xml(self, version, include_case_on_closed=False):
        from xml.etree import cElementTree as ElementTree
        from casexml.apps.phone.xml import get_case_element
        if self.closed:
            if include_case_on_closed:
                elem = get_case_element(self, ('create', 'update', 'close'), version)
            else:
                elem = get_case_element(self, ('close'), version)
        else:
            elem = get_case_element(self, ('create', 'update'), version)
        return ElementTree.tostring(elem)

    def get_attachment_server_url(self, name):
        """
        A server specific URL for remote clients to access case attachment resources async.
        """
        if name in self.case_attachments:
            from dimagi.utils import web
            from django.urls import reverse
            return "%s%s" % (web.get_url_base(),
                 reverse("api_case_attachment", kwargs={
                     "domain": self.domain,
                     "case_id": self.case_id,
                     "attachment_id": name,
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
