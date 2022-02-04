import collections
from abc import ABCMeta, abstractmethod

from memoized import memoized

from .mixin import CaseToXMLMixin


DEFAULT_PARENT_IDENTIFIER = 'parent'


def get_index_map(indices):
    return dict([
        (index.identifier, {
            "case_type": index.referenced_type,
            "case_id": index.referenced_id,
            "relationship": index.relationship,
        }) for index in indices
    ])


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

    def get_case_property(self, property, dynamic_only=False):
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

        if property_name == '_id':
            property_name = 'case_id'

        result.append(CasePropertyResult(
            self,
            self.get_case_property(property_name)
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
        from lxml import etree as ElementTree
        from casexml.apps.phone.xml import get_case_element
        if self.closed:
            if include_case_on_closed:
                elem = get_case_element(self, ('create', 'update', 'close'), version)
            else:
                elem = get_case_element(self, ('close'), version)
        else:
            elem = get_case_element(self, ('create', 'update'), version)
        return ElementTree.tostring(elem, encoding='utf-8')

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
