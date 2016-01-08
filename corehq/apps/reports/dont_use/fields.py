"""
DO NOT WRITE ANY NEW FUNCTIONALITY BASED ON THIS FILE
This is being kept around only to support legacy reports
"""
from django.template.context import Context
from django.template.loader import render_to_string
import pytz
import warnings
from corehq.apps.programs.models import Program
from corehq.apps.groups.models import Group
from corehq.apps.reports.models import HQUserType
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
import uuid
from corehq.apps.users.models import WebUser


class ReportField(object):
    slug = ""
    template = ""
    is_cacheable = False

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
    template = "reports/dont_use_fields/bootstrap2/select_generic.html"
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


class SelectMobileWorkerMixin(object):
    slug = "select_mw"
    name = ugettext_noop("Select Mobile Worker")

    @classmethod
    def get_default_text(cls, user_filter, default_option=None):
        default = default_option or cls.default_option
        if user_filter[HQUserType.ADMIN].show or \
           user_filter[HQUserType.DEMO_USER].show or user_filter[HQUserType.UNKNOWN].show:
            default = _('%s & Others') % _(default)
        return default


class BooleanField(ReportField):
    slug = "checkbox"
    label = "hello"
    template = "reports/partials/checkbox.html"

    def update_context(self):
        self.context['label'] = self.label
        self.context[self.slug] = self.request.GET.get(self.slug, False)
        self.context['checked'] = self.request.GET.get(self.slug, False)


class UserOrGroupField(ReportSelectField):
    """
        To Use: Subclass and specify what the field options should be
    """
    slug = "view_by"
    name = ugettext_noop("View by Users or Groups")
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


class ReportMultiSelectField(ReportSelectField):
    template = "reports/dont_use_fields/bootstrap2/multiselect_generic.html"
    selected = []
    # auto_select
    default_option = []

    # enfore as_combo = False ?

    def update_params(self):
        self.selected = self.request.GET.getlist(self.slug) or self.default_option


class MultiSelectGroupField(ReportMultiSelectField):
    slug = "group"
    name = ugettext_noop("Group")
    cssId = "group_select"
    default_option = ['_all']
    placeholder = 'Click to select groups'
    help_text = "Start typing to select one or more groups"

    @property
    def options(self):
        self.groups = Group.get_reporting_groups(self.domain)
        opts = [dict(val=group.get_id, text=group.name) for group in self.groups]
        opts.insert(0, {'text': 'All', 'val': '_all'})
        return opts
