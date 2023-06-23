from django.utils.translation import gettext as _

from corehq.apps.hqwebapp.templatetags.proptable_tags import DisplayConfig
from corehq.apps.users.util import cached_owner_id_to_display


def reference_case_attachment_view(request, domain, case_id, attachment_id):
    raise NotImplemented("This view is to be overrided by the specific implementations for retrieving case attachments")


class CaseDisplayWrapper(object):

    def __init__(self, case):
        self.case = case

    def actions(self):
        actions = self.case.to_json()['actions']
        return actions.reverse()

    def to_full_dict(self):
        """
        Include calculated properties that need to be available to the case
        details display by overriding this method.
        """
        json = self.case.to_json()
        json['status'] = _('Closed') if self.case.closed else _('Open')

        return json

    def get_display_config(self):
        return {
            "layout": [
                [
                    DisplayConfig(name=_("Name"), expr="name", has_history=True),
                    DisplayConfig(name=_("Opened On"), expr="opened_on", process="date", is_phone_time=True),
                    DisplayConfig(name=_("Modified On"), expr="modified_on", process="date", is_phone_time=True),
                    DisplayConfig(name=_("Closed On"), expr="closed_on", process="date", is_phone_time=True),
                ],
                [
                    DisplayConfig(name=_("Case Type"), expr="type", format="<code>{0}</code>"),
                    DisplayConfig(name=_("Last Submitter"), expr="user_id", process="doc_info"),
                    DisplayConfig(name=_("Owner"), expr="owner_id", process="doc_info", has_history=True),
                    DisplayConfig(name=_("Case ID"), expr="_id"),
                ],
            ],
        }

    def dynamic_properties(self):
        # pop seen properties off of remaining case properties
        dynamic_data = self.case.dynamic_case_properties()
        # hack - as of commcare 2.0, external id is basically a dynamic property
        # so also check and add it here
        if self.case.external_id:
            dynamic_data['external_id'] = self.case.external_id
        if self.case.location_id:
            dynamic_data['location_id'] = self.case.location_id

        dynamic_data['case_name'] = self.case.name

        return dynamic_data

    @property
    def related_cases_columns(self):
        return [
            DisplayConfig(name=_('Status'), expr='status'),
            DisplayConfig(name=_('Case Type'), expr='type'),
            DisplayConfig(name=_('Owner'), expr=lambda c: cached_owner_id_to_display(c.get('owner_id'))),
            DisplayConfig(name=_('Date Opened'), expr='opened_on', process="date", is_phone_time=True),
            DisplayConfig(name=_('Date Modified'), expr='modified_on', process="date", is_phone_time=True),
        ]

    @property
    def related_type_info(self):
        return None


class SupplyPointDisplayWrapper(CaseDisplayWrapper):

    def to_full_dict(self):
        from corehq.apps.locations.models import SQLLocation
        data = super(SupplyPointDisplayWrapper, self).to_full_dict()
        data.update({
            'location_type': None,
            'location_site_code': None,
            'location_parent_name': None,
        })
        try:
            location = SQLLocation.objects.get(location_id=self.case.location_id)
        except (SQLLocation.DoesNotExist, AttributeError):
            pass
        else:
            data['location_type'] = location.location_type_name
            data['location_site_code'] = location.site_code
            if location.parent:
                data['location_parent_name'] = location.parent.name

        return data

    def get_display_config(self):
        return {
            "layout": [
                [
                    DisplayConfig(name=_("Name"), expr="name"),
                    DisplayConfig(name=_("Type"), expr="location_type"),
                    DisplayConfig(name=_("Code"), expr="location_site_code"),
                ],
                [
                    DisplayConfig(name=_("Parent Location"), expr="location_parent_name"),
                    DisplayConfig(name=_("Location"), expr="owner_id"),
                    DisplayConfig(name=_("Location"), expr="owner_id", process="doc_info"),
                ],
            ],
        }


def get_wrapped_case(case):
    from corehq.apps.commtrack import const
    wrapper_class = {
        const.SUPPLY_POINT_CASE_TYPE: SupplyPointDisplayWrapper,
    }.get(case.type, CaseDisplayWrapper)
    return wrapper_class(case)
