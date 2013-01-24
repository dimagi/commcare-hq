import datetime
from django.template.context import Context
from django.template.loader import render_to_string
import pytz
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.orgs.models import Organization
from corehq.apps.reports import util
from corehq.apps.groups.models import Group
from corehq.apps.reports.filters.base import BaseReportFilter
from corehq.apps.reports.models import HQUserType
from corehq.apps.locations.models import Location
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.datespan import datespan_in_request
from corehq.apps.locations.models import location_tree, root_locations
from corehq.apps.locations.util import load_locs_json
import settings
import json
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.reports.cache import CacheableRequestMixIn, request_cache
from django.core.urlresolvers import reverse
import uuid

"""
    Note: Fields is being phased out in favor of filters.
    The only reason it still exists is because admin reports needs to get moved over to the new
    reporting structure.
"""

datespan_default = datespan_in_request(
            from_param="startdate",
            to_param="enddate",
            default_days=7,
        )

class ReportField(CacheableRequestMixIn):
    slug = ""
    template = ""
    context = Context()

    def __init__(self, request, domain=None, timezone=pytz.utc, parent_report=None):
        self.request = request
        self.domain = domain
        self.timezone = timezone
        self.parent_report = parent_report

    def render(self):
        if not self.template: return ""
        self.context["slug"] = self.slug
        self.update_context()
        return render_to_string(self.template, self.context)

    def update_context(self):
        """
        If your select field needs some context (for example, to set the default) you can set that up here.
        """
        pass

class ReportSelectField(ReportField):
    slug = "generic_select"
    name = ugettext_noop("Generic Select")
    template = "reports/fields/select_generic.html"
    default_option = ugettext_noop("Select Something...")
    options = [dict(val="val", text="text")]
    cssId = "generic_select_box"
    cssClasses = "span4"
    selected = None
    hide_field = False
    as_combo = False

    def __init__(self, *args, **kwargs):
        super(ReportSelectField, self).__init__(*args, **kwargs)
        # need to randomize cssId so knockout bindings won't clobber each other
        # when multiple select controls on screen at once
        nonce = uuid.uuid4().hex[-12:]
        self.cssId = '%s-%s' % (self.cssId, nonce)

    def update_params(self):
        self.selected = self.request.GET.get(self.slug)

    def update_context(self):
        self.update_params()
        self.context['hide_field'] = self.hide_field
        self.context['select'] = dict(
            options=self.options,
            default=self.default_option,
            cssId=self.cssId,
            cssClasses=self.cssClasses,
            label=self.name,
            selected=self.selected,
            use_combo_box=self.as_combo,
        )

class ReportMultiSelectField(ReportSelectField):
    template = "reports/fields/multiselect_generic.html"
    selected = []
    default_option = []

    # enfore as_combo = False ?

    def update_params(self):
        self.selected = self.request.GET.getlist(self.slug) or self.default_option

class MonthField(ReportField):
    slug = "month"
    template = "reports/partials/month-select.html"

    def update_context(self):
        self.context['month'] = self.request.GET.get('month', datetime.datetime.utcnow().month)

class YearField(ReportField):
    slug = "year"
    template = "reports/partials/year-select.html"

    def update_context(self):
        year = getattr(settings, 'START_YEAR', 2008)
        self.context['years'] = range(year, datetime.datetime.utcnow().year + 1)
        self.context['year'] = int(self.request.GET.get('year', datetime.datetime.utcnow().year))

class GroupField(ReportSelectField):
    slug = "group"
    name = ugettext_noop("Group")
    default_option = ugettext_noop("Everybody")
    cssId = "group_select"

    def update_params(self):
        super(GroupField, self).update_params()
        self.groups = Group.get_reporting_groups(self.domain)
        self.options = [dict(val=group.get_id, text=group.name) for group in self.groups]

class SelectReportingGroupField(GroupField):
    name = ugettext_noop("Reporting Group")
    default_option = ugettext_noop("All Groups")
    cssClasses = "span6"

    def update_params(self):
        super(SelectReportingGroupField, self).update_params()
        individual = self.request.GET.get('individual', '')
        if individual:
            try:
                group = Group.get(individual)
            except Exception:
                group = None
            if group:
                self.hide_field = True
        self.options = [dict(val=group.get_id, text=group.name) for group in self.groups if not group.case_sharing]

class FilterUsersField(ReportField):
    slug = "ufilter"
    template = "reports/fields/filter_users.html"

    def update_context(self):
        toggle, show_filter = self.get_user_filter(self.request)
        self.context['show_user_filter'] = show_filter
        self.context['toggle_users'] = toggle

    @classmethod
    def get_user_filter(cls, request):
        ufilter = group = individual = None
        try:
            if request.GET.get('ufilter', ''):
                ufilter = request.GET.getlist('ufilter')
            group = request.GET.get('group', '')
            individual = request.GET.get('individual', '')
        except KeyError:
            pass
        show_filter = True
        toggle = HQUserType.use_defaults()
        if ufilter and not (group or individual):
            toggle = HQUserType.use_filter(ufilter)
        elif group or individual:
            show_filter = False
        return toggle, show_filter

class CaseTypeField(ReportSelectField):
    slug = "case_type"
    name = ugettext_noop("Case Type")
    cssId = "case_type_select"

    def update_params(self):
        case_types = self.get_case_types(self.domain)
        case_type = self.request.GET.get(self.slug, '')

        self.selected = case_type
        self.options = [dict(val=case, text="%s" % case) for case in case_types]
        self.default_option = _("All Case Types")

    @classmethod
    def get_case_types(cls, domain):
        key = [domain]
        for r in get_db().view('hqcase/all_cases',
            startkey=key,
            endkey=key + [{}],
            group_level=2
        ).all():
            _, case_type = r['key']
            if case_type:
                yield case_type

    @classmethod
    def get_case_counts(cls, domain, case_type=None, user_ids=None):
        """
        Returns open count, all count
        """
        user_ids = user_ids or [{}]
        for view_name in ('hqcase/open_cases', 'hqcase/all_cases'):
            def individual_counts():
                for user_id in user_ids:
                    key = [domain, case_type or {}, user_id]
                    try:
                        yield get_db().view(view_name,
                            startkey=key,
                            endkey=key + [{}],
                            group_level=0
                        ).one()['value']
                    except TypeError:
                        yield 0
            yield sum(individual_counts())

class SelectFormField(ReportSelectField):
    slug = "form"
    name = ugettext_noop("Form Type")
    cssId = "form_select"
    cssClasses = "span6"
    default_option = ugettext_noop("Select a Form")

    def update_params(self):
        self.options = util.form_list(self.domain)
        self.selected = self.request.GET.get(self.slug, None)

class SelectAllFormField(SelectFormField):
    default_option = ugettext_noop("Show All Forms")

class SelectOpenCloseField(ReportSelectField):
    slug = "is_open"
    name = ugettext_noop("Opened / Closed")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "Show All"
    options = [dict(val="open", text=ugettext_noop("Only Open")),
               dict(val="closed", text=ugettext_noop("Only Closed"))]

class SelectApplicationField(ReportSelectField):
    slug = "app"
    name = ugettext_noop("Application")
    cssId = "application_select"
    cssClasses = "span6"
    default_option = ugettext_noop("Select Application [Latest Build Version]")

    def update_params(self):
        apps_for_domain = get_db().view("app_manager/applications_brief",
            startkey=[self.domain],
            endkey=[self.domain, {}],
            include_docs=True).all()
        available_apps = [dict(val=app['value']['_id'],
                                text=_("%(name)s [up to build %(version)s]") % {
                                    'name': app['value']['name'], 
                                    'version': app['value']['version']})
                          for app in apps_for_domain]
        self.selected = self.request.GET.get(self.slug,'')
        self.options = available_apps

class SelectOrganizationField(ReportSelectField):
    slug = "org"
    name = ugettext_noop("Organization")
    cssId = "organization_select"
    cssClasses = "span6"
    default_option = ugettext_noop("All Organizations")

    def update_params(self):
        available_orgs = [{'val': o.name, 'text': o.title} for o in  Organization.get_all()]
        self.selected = self.request.GET.get(self.slug,'')
        self.options = available_orgs

class SelectCategoryField(ReportSelectField):
    slug = "category"
    name = ugettext_noop("Category")
    cssId = "category_select"
    cssClasses = "span6"
    default_option = ugettext_noop("All Categories")

    def update_params(self):
        if hasattr(Domain, 'categories'):
            available_categories = [{'val': d.replace(' ', '+'), 'text': d} for d in Domain.categories()]
        else:
            available_categories = []
        self.selected = self.request.GET.get(self.slug,'')
        self.options = available_categories

class SelectLicenseField(ReportSelectField):
    slug = "license"
    name = ugettext_noop("License")
    cssId = "license_select"
    cssClasses = "span6"
    default_option = ugettext_noop("All Licenses")

    def update_params(self):
        available_licenses = [{'val': code, 'text': license} for code, license in LICENSES.items()]
        self.selected = self.request.GET.get(self.slug,'')
        self.options = available_licenses

class SelectRegionField(ReportSelectField):
    slug = "region"
    name = ugettext_noop("Region")
    cssId = "region_select"
    cssClasses = "span6"
    default_option = ugettext_noop("All Regions")

    def update_params(self):
        if hasattr(Domain, 'regions'):
            available_regions = [{'val': d.replace(' ', '+'), 'text': d} for d in Domain.regions()]
        else:
            available_regions = []
        self.selected = self.request.GET.get(self.slug,'')
        self.options = available_regions


class SelectMobileWorkerField(ReportField):
    slug = "select_mw"
    template = "reports/fields/select_mobile_worker.html"
    name = ugettext_noop("Select Mobile Worker")
    default_option = ugettext_noop("All Mobile Workers")

    def update_params(self):
        pass

    def update_context(self):
        self.user_filter, _ = FilterUsersField.get_user_filter(self.request)
        self.individual = self.request.GET.get('individual', '')
        self.default_option = self.get_default_text(self.user_filter)
        self.users = util.user_list(self.domain)

        self.update_params()

        self.context['field_name'] = self.name
        self.context['default_option'] = self.default_option
        self.context['users'] = self.users
        self.context['individual'] = self.individual

    @classmethod
    def get_default_text(cls, user_filter):
        default = cls.default_option
        if user_filter[HQUserType.ADMIN].show or \
           user_filter[HQUserType.DEMO_USER].show or user_filter[HQUserType.UNKNOWN].show:
            default = _('%s & Others') % _(default)
        return default

class SelectCaseOwnerField(SelectMobileWorkerField):
    name = ugettext_noop("Select Case Owner")
    default_option = ugettext_noop("All Case Owners")

    def update_params(self):
        case_sharing_groups = Group.get_case_sharing_groups(self.domain)
        self.context["groups"] = [dict(group_id=group._id, name=group.name) for group in case_sharing_groups]


class SelectFilteredMobileWorkerField(SelectMobileWorkerField):
    """
        This is a little field for use when a client really wants to filter by
        individuals from a specific group.  Since by default we still want to
        show all the data, no filtering is done unless the special group filter
        is selected.
    """
    slug = "select_filtered_mw"
    name = ugettext_noop("Select Mobile Worker")
    template = "reports/fields/select_filtered_mobile_worker.html"
    default_option = ugettext_noop("All Mobile Workers...")

    # Whether to display both the default option and "Only <group> Mobile
    # Workers" or just the default option (useful when using a single
    # group_name and changing default_option to All <group> Workers
    show_only_group_option = True

    group_names = []

    def update_params(self):
        if not self.individual:
            self.individual = self.request.GET.get('filtered_individual', '')
        self.users = []
        self.group_options = []
        for group in self.group_names:
            filtered_group = Group.by_name(self.domain, group)
            if filtered_group:
                if self.show_only_group_option:
                    self.group_options.append(dict(group_id=filtered_group._id,
                        name=_("Only %s Mobile Workers") % group))
                self.users.extend(filtered_group.get_users(is_active=True, only_commcare=True))

    def update_context(self):
        super(SelectFilteredMobileWorkerField, self).update_context()
        self.context['users'] = self.users_to_options(self.users)
        self.context['group_options'] = self.group_options

    @staticmethod
    def users_to_options(user_list):
        return [dict(val=user.user_id,
            text=user.raw_username,
            is_active=user.is_active) for user in user_list]


class DatespanField(ReportField):
    name = ugettext_noop("Date Range")
    slug = "datespan"
    template = "reports/fields/datespan.html"

    def update_context(self):
        self.context["datespan_name"] = self.name
        self.datespan = DateSpan.since(7, format="%Y-%m-%d", timezone=self.timezone)
        if self.request.datespan.is_valid():
            self.datespan.startdate = self.request.datespan.startdate
            self.datespan.enddate = self.request.datespan.enddate
        self.context['timezone'] = self.timezone.zone
        self.context['datespan'] = self.datespan

class LocationField(ReportField):
    name = ugettext_noop("Location")
    slug = "location"
    template = "reports/fields/location.html"
    is_cacheable = True

    def update_context(self):
        self.context.update(self._get_custom_context())

    @request_cache('locationfieldcontext')
    def _get_custom_context(self):
        all_locs = location_tree(self.domain)
        def loc_to_json(loc):
            return {
                'name': loc.name,
                'type': loc.location_type,
                'uuid': loc._id,
                'children': [loc_to_json(child) for child in loc._children],
            }
        loc_json = [loc_to_json(root) for root in all_locs]

        return {
            'control_name': self.name,
            'control_slug': self.slug,
            'loc_id': self.request.GET.get('location_id'),
            'locations': json.dumps(loc_json)
        }

class AsyncLocationField(ReportField):
    name = ugettext_noop("Location")
    slug = "location_async"
    template = "reports/fields/location_async.html"

    def update_context(self):
        self.context.update(self._get_custom_context())

    def _get_custom_context(self):
        api_root = reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'location', 
                                                        'api_name': 'v0.3'})
        selected_loc_id = self.request.GET.get('location_id')

        return {
            'api_root': api_root,
            'control_name': self.name,
            'control_slug': self.slug,
            'loc_id': selected_loc_id,
            'locations': json.dumps(load_locs_json(self.domain, selected_loc_id)),
        }

class AsyncDrillableField(BaseReportFilter):
    # todo: add documentation
    """
    example_hierarchy = [{"type": "state", "display": "name"},
                         {"type": "district", "parent_ref": "state_id", "references": "id", "display": "name"},
                         {"type": "block", "parent_ref": "district_id", "references": "id", "display": "name"},
                         {"type": "village", "parent_ref": "block_id", "references": "id", "display": "name"}]
    """
    template = "reports/fields/drillable_async.html"
    hierarchy = [] # a list of fixture data type names that representing different levels of the hierarchy. Starting with the root

    def fdi_to_json(self, fdi):
        return {
            'fixture_type': fdi.data_type_id,
            'fields': fdi.fields,
            'id': fdi.get_id,
            'children': getattr(fdi, '_children', None),
        }

    fdts = {}
    def data_types(self, index=None):
        if not self.fdts:
            self.fdts = [FixtureDataType.by_domain_tag(self.domain, h["type"]).one() for h in self.hierarchy]
        return self.fdts if index is None else self.fdts[index]

    @property
    def api_root(self):
        return reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'fixture',
                                                        'api_name': 'v0.1'})

    @property
    def full_hierarchy(self):
        ret = []
        for i, h in enumerate(self.hierarchy):
            new_h = dict(h)
            new_h['id'] = self.data_types(i).get_id
            ret.append(new_h)
        return ret

    @property
    def filter_context(self):
        f_id = self.request.GET.get('fixture_id', None)
        selected_fdi_type = f_id.split(':')[0] if f_id else None
        selected_fdi_id = f_id.split(':')[1] if f_id else None

        index = 0
        if selected_fdi_id:
            for i, h in enumerate(self.hierarchy[::-1]):
                if h['type'] == selected_fdi_type:
                    index = i

            cur_fdi = FixtureDataItem.get(selected_fdi_id)
            siblings = list(FixtureDataItem.by_data_type(self.domain, cur_fdi.data_type_id))
            for i, h in enumerate(self.full_hierarchy[::-1]):
                if i < index: continue
                if h.get('parent_ref', None):
                    ngdt_id = self.full_hierarchy[len(self.full_hierarchy) - (i+2)]['id']
                    next_gen = list(FixtureDataItem.by_data_type(self.domain, ngdt_id))
                else:
                    next_gen = []

                if next_gen:
                    parent = [f for f in next_gen if f.fields['id'] == cur_fdi.fields[h['parent_ref']]][0]
                    parent._children = [self.fdi_to_json(fdi) for fdi in siblings]
                    cur_fdi, siblings = parent, next_gen

        else:
            siblings = list(FixtureDataItem.by_data_type(self.domain, self.data_types(0).get_id))

        return {
            'api_root': self.api_root,
            'control_name': self.label,
            'control_slug': self.slug,
            'selected_fdi_id': selected_fdi_id,
            'fdis': json.dumps([self.fdi_to_json(fdi) for fdi in siblings]),
            'hierarchy': self.full_hierarchy
        }
        
class DeviceLogTagField(ReportField):
    slug = "logtag"
    errors_only_slug = "errors_only"
    template = "reports/fields/devicelog_tags.html"

    def update_context(self):
        errors_only = bool(self.request.GET.get(self.errors_only_slug, False))
        self.context['errors_only_slug'] = self.errors_only_slug
        self.context[self.errors_only_slug] = errors_only

        selected_tags = self.request.GET.getlist(self.slug)
        show_all = bool(not selected_tags)
        self.context['default_on'] = show_all
        data = get_db().view('phonelog/device_log_tags', group=True)
        tags = [dict(name=item['key'],
                    show=bool(show_all or item['key'] in selected_tags))
                    for item in data]
        self.context['logtags'] = tags
        self.context['slug'] = self.slug

class DeviceLogFilterField(ReportField):
    slug = "logfilter"
    template = "reports/fields/devicelog_filter.html"
    view = "phonelog/devicelog_data"
    filter_desc = "Filter Logs By"

    def update_context(self):
        selected = self.request.GET.getlist(self.slug)
        show_all = bool(not selected)
        self.context['default_on'] = show_all

        data = get_db().view(self.view,
            startkey = [self.domain],
            endkey = [self.domain, {}],
            group=True)
        filters = [dict(name=item['key'][-1],
                    show=bool(show_all or item['key'][-1] in selected))
                        for item in data]
        self.context['filters'] = filters
        self.context['slug'] = self.slug
        self.context['filter_desc'] = self.filter_desc

class DeviceLogUsersField(DeviceLogFilterField):
    slug = "loguser"
    view = "phonelog/devicelog_data_users"
    filter_desc = ugettext_noop("Filter Logs by Username")

class DeviceLogDevicesField(DeviceLogFilterField):
    slug = "logdevice"
    view = "phonelog/devicelog_data_devices"
    filter_desc = ugettext_noop("Filter Logs by Device")
