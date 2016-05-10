import collections
import logging
from abc import ABCMeta, abstractmethod

import six as six
from couchdbkit import ResourceNotFound
from decimal import Decimal

from corehq.apps.commtrack.const import DAYS_IN_MONTH
from dimagi.utils.decorators.memoized import memoized
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

    def get_subcases(self, index_identifier=None):
        raise NotImplementedError

    def get_parent(self, identifier=None, relationship=None):
        raise NotImplementedError

    def get_case_property(self, property):
        raise NotImplementedError

    def to_json(self):
        raise NotImplementedError()

    def to_api_json(self):
        raise NotImplementedError()

    def _resolve_case_property(self, property_name, result):
        CasePropertyResult = collections.namedtuple('CasePropertyResult', 'case value')

        if property_name.lower().startswith('parent/'):
            parents = self.get_parent(identifier=DEFAULT_PARENT_IDENTIFIER)
            for parent in parents:
                parent._resolve_case_property(property_name[7:], result)
            return

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


class AbstractLedgerValue(object):
    @property
    def months_remaining(self):
        from casexml.apps.stock.utils import months_of_stock_remaining
        return months_of_stock_remaining(
            self.stock_on_hand,
            self.get_daily_consumption()
        )

    @property
    def resupply_quantity_needed(self):
        monthly_consumption = self.get_monthly_consumption()
        if monthly_consumption is not None and self.sql_location is not None:
            overstock = self.sql_location.location_type.overstock_threshold
            needed_quantity = int(
                monthly_consumption * overstock
            )
            return int(max(needed_quantity - self.stock_on_hand, 0))
        else:
            return None

    @property
    def stock_category(self):
        from casexml.apps.stock.utils import state_stock_category
        return state_stock_category(self)

    @memoized
    def get_domain(self):
        from corehq.apps.domain.models import Domain
        return Domain.get_by_name(
            self.domain
        )

    def get_daily_consumption(self):
        if self.daily_consumption is not None:
            return self.daily_consumption
        else:
            monthly = self._get_default_monthly_consumption()
            if monthly is not None:
                return Decimal(monthly) / Decimal(DAYS_IN_MONTH)

    def get_monthly_consumption(self):

        if self.daily_consumption is not None:
            return self.daily_consumption * Decimal(DAYS_IN_MONTH)
        else:
            return self._get_default_monthly_consumption()

    def _get_default_monthly_consumption(self):
        from casexml.apps.stock.consumption import compute_default_monthly_consumption
        domain = self.get_domain()
        if domain and domain.commtrack_settings:
            config = domain.commtrack_settings.get_consumption_config()
        else:
            return None

        return compute_default_monthly_consumption(
            self.case_id,
            self.product_id,
            config
        )
