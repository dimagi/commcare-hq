from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext as _
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
        return [
            {
                "layout": [
                    [
                        {
                            "expr": "name",
                            "name": _("Name"),
                        },
                        {
                            "expr": "opened_on",
                            "name": _("Opened On"),
                            "parse_date": True,
                            'is_phone_time': True,
                        },
                        {
                            "expr": "modified_on",
                            "name": _("Modified On"),
                            "parse_date": True,
                            "is_phone_time": True,
                        },
                        {
                            "expr": "closed_on",
                            "name": _("Closed On"),
                            "parse_date": True,
                            "is_phone_time": True,
                        },
                    ],
                    [
                        {
                            "expr": "type",
                            "name": _("Case Type"),
                            "format": '<code>{0}</code>',
                        },
                        {
                            "expr": "user_id",
                            "name": _("Last Submitter"),
                            "process": 'doc_info',
                        },
                        {
                            "expr": "owner_id",
                            "name": _("Owner"),
                            "process": 'doc_info',
                        },
                        {
                            "expr": "_id",
                            "name": _("Case ID"),
                        },
                    ],
                ],
            }
        ]

    def dynamic_properties(self):
        # pop seen properties off of remaining case properties
        dynamic_data = self.case.dynamic_case_properties()
        # hack - as of commcare 2.0, external id is basically a dynamic property
        # so also check and add it here
        if self.case.external_id:
            dynamic_data['external_id'] = self.case.external_id

        return dynamic_data

    @property
    def related_cases_columns(self):
        return [
            {
                'name': _('Status'),
                'expr': "status"
            },
            {
                'name': _('Case Type'),
                'expr': "type",
            },
            {
                'name': _('Owner'),
                'expr': lambda c: cached_owner_id_to_display(c.get('owner_id')),
            },
            {
                'name': _('Date Opened'),
                'expr': "opened_on",
                'parse_date': True,
                "is_phone_time": True,
            },
            {
                'name': _('Date Modified'),
                'expr': "modified_on",
                'parse_date': True,
                "is_phone_time": True,
            }
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
        return [
            {
                "layout": [
                    [
                        {
                            "expr": "name",
                            "name": _("Name"),
                        },
                        {
                            "expr": "location_type",
                            "name": _("Type"),
                        },
                        {
                            "expr": "location_site_code",
                            "name": _("Code"),
                        },
                    ],
                    [
                        {
                            "expr": "location_parent_name",
                            "name": _("Parent Location"),
                        },
                        {
                            "expr": "owner_id",
                            "name": _("Location"),
                            "process": "doc_info",
                        },
                    ],
                ],
            }
        ]


def get_wrapped_case(case):
    from corehq.apps.commtrack import const
    wrapper_class = {
        const.SUPPLY_POINT_CASE_TYPE: SupplyPointDisplayWrapper,
    }.get(case.type, CaseDisplayWrapper)
    return wrapper_class(case)
