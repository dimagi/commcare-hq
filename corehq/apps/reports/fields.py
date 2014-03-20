import datetime
from django.template.context import Context
from django.template.loader import render_to_string
import pytz
import warnings
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.models import Location, Program
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.orgs.models import Organization
from corehq.apps.reports import util
from corehq.apps.groups.models import Group
from corehq.apps.reports.filters.base import BaseReportFilter, BaseSingleOptionFilter
from corehq.apps.reports.models import HQUserType
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.datespan import datespan_in_request
from corehq.apps.locations.util import load_locs_json, location_hierarchy_config
from django.conf import settings
import json
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.reports.cache import CacheableRequestMixIn, request_cache
from django.core.urlresolvers import reverse
import uuid
from corehq.apps.users.models import WebUser

"""
    Note: Fields is being phased out in favor of filters.
    The only reason it still exists is because admin reports needs to get moved over to the new
    reporting structure.
"""

# TODO: Delete this file and corehq/apps/reports/fields.py.orig
# TODO: Delete from here
class ReportField(CacheableRequestMixIn):
    slug = ""
    template = ""

    def __init__(self, request, domain=None, timezone=pytz.utc, parent_report=None):
        warnings.warn(
            "ReportField (%s) is deprecated. Use ReportFilter instead." % (
                self.__class__.__name__
            ),
            DeprecationWarning,
        )
        self.context = Context()
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
    placeholder = ''
    help_text = ''

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
        self.context['help_text'] = self.help_text
        self.context['select'] = dict(
            options=self.options,
            default=self.default_option,
            cssId=self.cssId,
            cssClasses=self.cssClasses,
            label=self.name,
            selected=self.selected,
            use_combo_box=self.as_combo,
            placeholder=self.placeholder,
        )


class FilterUsersField(ReportField):
    slug = "ufilter"
    template = "reports/fields/filter_users.html"
    always_show_filter = False
    can_be_empty = False

    def update_context(self):
        toggle, show_filter = self.get_user_filter(self.request)
        self.context['show_user_filter'] = show_filter
        self.context['toggle_users'] = toggle
        self.context['can_be_empty'] = self.can_be_empty

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
        except AttributeError:
            pass

        show_filter = True
        toggle = HQUserType.use_defaults()

        if not cls.always_show_filter and (group or individual):
            show_filter = False
        elif ufilter:
            toggle = HQUserType.use_filter(ufilter)
        return toggle, show_filter

# TODO: Delete to here


class BooleanField(ReportField):
    slug = "checkbox"
    label = "hello"
    template = "reports/partials/checkbox.html"

    def update_context(self):
        self.context['label'] = self.label
        self.context[self.slug] = self.request.GET.get(self.slug, False)
        self.context['checked'] = self.request.GET.get(self.slug, False)


class StrongFilterUsersField(FilterUsersField):
    """
        Version of the FilterUsersField that always actually uses and shows this filter
        When using this field:
            use SelectMobileWorkerFieldHack instead of SelectMobileWorkerField
            if using ProjectReportParametersMixin make sure filter_users_field_class is set to this
    """
    always_show_filter = True
    can_be_empty = True


class UserOrGroupField(ReportSelectField):
    """
        To Use: Subclass and specify what the field options should be
    """
    slug = "view_by"
    name = "View by Users or Groups"
    cssId = "view_by_select"
    cssClasses = "span2"
    default_option = "Users"

    def update_params(self):
        self.selected = self.request.GET.get(self.slug, '')
        self.options = [{'val': 'groups', 'text': 'Groups'}]


class SelectProgramField(ReportSelectField):
    slug = "program"
    name = ugettext_noop("Program")
    cssId = "program_select"
    default_option = 'All'

    def update_params(self):
        self.selected = self.request.GET.get('program')
        user = WebUser.get_by_username(str(self.request.user))
        if not self.selected and \
           self.selected != '' and \
           user.get_domain_membership(self.domain):
            self.selected = user.get_domain_membership(self.domain).program_id
        self.programs = Program.by_domain(self.domain)
        opts = [dict(val=program.get_id, text=program.name) for program in self.programs]
        self.options = opts
