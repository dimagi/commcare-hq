import json
import dateutil
from django import forms
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.groups.models import Group
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.util import group_filter, users_matching_filter, \
    users_filter, datespan_export_filter, app_export_filter, case_group_filter, \
    case_users_filter, datespan_from_beginning
from corehq.apps.style.crispy import B3MultiField, CrispyTemplate
from corehq.apps.style.forms.widgets import Select2MultipleChoiceWidget, \
    DateRangePickerWidget
from couchexport.util import SerializableFunction

from crispy_forms.bootstrap import FormActions, InlineField
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from crispy_forms.layout import Layout
from dimagi.utils.dates import DateSpan


class CreateFormExportForm(forms.Form):
    application = forms.CharField(required=False)
    module = forms.CharField(required=False)
    form = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super(CreateFormExportForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-2'
        self.helper.field_class = 'col-sm-10'

        self.helper.layout = crispy.Layout(
            crispy.Field(
                'application',
                placeholder=_("Select Application"),
                ng_model="createForm.application",
                ng_change="updateModules()",
                ng_required="true",
            ),
            crispy.Field(
                'module',
                placeholder=_("Select Module"),
                ng_model="createForm.module",
                ng_disabled="!createForm.application",
                ng_change="updateForms()",
                ng_required="true",
            ),
            crispy.Field(
                'form',
                placeholder=_("Select Form"),
                ng_model="createForm.form",
                ng_disabled="!createForm.module",
                ng_required="true",
            ),
        )


class CreateCaseExportForm(forms.Form):
    application = forms.CharField(required=False)
    case_type = forms.CharField(
        required=False,
        help_text=mark_safe(
            '<span ng-show="!!hasNoCaseTypes '
            '&& !!createForm.application">{}</span>'.format(
            ugettext_noop("""Note: This application does not appear to be using
            <a href="https://wiki.commcarehq.org/display/commcarepublic/Case+Management">
            case management</a>.""")
        )),
    )

    def __init__(self, *args, **kwargs):
        super(CreateCaseExportForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-2'
        self.helper.field_class = 'col-sm-10'

        self.helper.layout = crispy.Layout(
            crispy.Field(
                'application',
                placeholder=_("Select Application"),
                ng_model="createForm.application",
                ng_change="updateCaseTypes()",
                ng_required="true",
            ),
            crispy.Field(
                'case_type',
                placeholder=_("Select Case Type"),
                ng_model="createForm.case_type",
                ng_disabled="!createForm.application",
                ng_required="true",
            ),
        )


class FilterExportDownloadForm(forms.Form):

    _USER_MOBILE = 'mobile'
    _USER_DEMO = 'demo_user'
    _USER_ADMIN = 'admin'
    _USER_UNKNOWN = 'unknown'
    _USER_SUPPLY = 'supply'

    _USER_TYPES_CHOICES = [
        (_USER_MOBILE, ugettext_noop("All Mobile Workers")),
        (_USER_DEMO, ugettext_noop("Demo User")),
        (_USER_ADMIN, ugettext_noop("Admin User")),
        (_USER_UNKNOWN, ugettext_noop("Unknown Users")),
        (_USER_SUPPLY, ugettext_noop("CommCare Supply")), # todo filter out supply
    ]
    type_or_group = forms.ChoiceField(
        label=ugettext_noop("User Types or Group"),
        required=False,
        choices=(
            ('type', ugettext_noop("User Types")),
            ('group', ugettext_noop("Group")),
        )
    )
    user_types = forms.MultipleChoiceField(
        label=ugettext_noop("Select User Types"),
        widget=Select2MultipleChoiceWidget,
        choices=_USER_TYPES_CHOICES,
        required=False,
    )
    group = forms.CharField(
        label=ugettext_noop("Select Group"),
        required=False,
    )
    date_range = forms.CharField(
        label=ugettext_noop("Date Range"),
        required=True,
        widget=DateRangePickerWidget(),
    )

    def __init__(self, domain, timezone, *args, **kwargs):
        self.domain = domain
        self.timezone = timezone
        super(FilterExportDownloadForm, self).__init__(*args, **kwargs)
        self.fields['date_range'].help_text = _(
            "The timezone for this export is %(timezone)s."
        ) % {
            'timezone': self.timezone,
        }
        default_datespan = datespan_from_beginning(self.domain, 7, self.timezone)
        self.fields['date_range'].widget = DateRangePickerWidget(
            default_datespan=default_datespan
        )

        initial = kwargs.get('initial', {})
        if initial.get('export_id'):
            self.fields['export_id'].widget = forms.HiddenInput()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3'
        self.helper.field_class = 'col-sm-5'
        self.helper.layout = Layout(
            crispy.Field(
                'type_or_group',
                ng_model="formData.type_or_group",
                ng_required='false',
            ),
            crispy.Div(
                crispy.Field(
                    'user_types',
                    ng_model='formData.user_types',
                    ng_required='false',
                ),
                ng_show="formData.type_or_group === 'type'",
            ),
            crispy.Div(
                B3MultiField(
                    _("Group"),
                    crispy.Div(
                        crispy.Div(
                            InlineField(
                                'group',
                                ng_model='formData.group',
                                ng_required='false',
                                style="width: 98%",
                            ),
                            ng_show="hasGroups",
                        ),
                    ),
                    CrispyTemplate('export/crispy_html/groups_help.html', {
                        'domain': self.domain,
                    }),
                ),
                ng_show="formData.type_or_group === 'group'",
            ),

            crispy.Field(
                'date_range',
                ng_model='formData.date_range',
                ng_required='true',
            ),
        )

    def _get_filtered_users(self):
        user_types = self.cleaned_data['user_types']
        # this STUPID. todo fix
        user_filter_toggles = [
            self._USER_MOBILE in user_types,
            self._USER_DEMO in user_types,
            self._USER_ADMIN in user_types,
            self._USER_UNKNOWN in user_types,
            self._USER_SUPPLY in user_types
        ]
        user_filters = HQUserType._get_manual_filterset(
            (True,) * HQUserType.count,
            user_filter_toggles
        )
        return users_matching_filter(self.domain, user_filters)

    def _get_group(self):
        group = self.cleaned_data['group']
        if group:
            return Group.get(group)


class FilterFormExportDownloadForm(FilterExportDownloadForm):
    """The filters for Form Export Download
    """

    def _get_user_or_group_filter(self):
        group = self._get_group()
        if group:
            # filter by groups
            return SerializableFunction(group_filter, group=group)
        # filter by users
        return SerializableFunction(users_filter,
                                    users=self._get_filtered_users())

    def _get_datespan_filter(self):
        date_range = self.cleaned_data['date_range']
        print "date_range", date_range
        dates = date_range.split(DateRangePickerWidget.separator)
        print "dates", dates
        startdate = dateutil.parser.parse(dates[0])
        enddate = dateutil.parser.parse(dates[1])
        datespan = DateSpan(startdate, enddate)
        if datespan.is_valid():
            datespan.set_timezone(self.timezone)
            return SerializableFunction(datespan_export_filter,
                                        datespan=datespan)

    def get_form_filter(self):
        # todo is app_id ever not None for custom exports?
        form_filter = SerializableFunction(app_export_filter, app_id=None)

        datespan_filter = self._get_datespan_filter()
        if datespan_filter:
            form_filter &= datespan_filter
        form_filter &= self._get_user_or_group_filter()
        # '&export_tag=["'+self.domain+'","'+xmlns+'","' + fileName +'"]' +
        return form_filter


    def format_export_data(self, export):
        from corehq.apps.export.views import EditCustomFormExportView
        return {
            'export_id': export.get_id,
            'xmlns': export.xmlns if hasattr(export, 'xmlns') else '',
            'export_type': 'form',
            'name': export.name,
            'edit_url': reverse(EditCustomFormExportView.urlname,
                                args=(self.domain, export.get_id)),
        }


class FilterCaseExportDownloadForm(FilterExportDownloadForm):

    def get_case_filter(self):
        group = self._get_group()
        if group:
            return SerializableFunction(case_group_filter, group=group)
        case_sharing_groups = [g.get_id for g in
                               Group.get_case_sharing_groups(self.domain)]
        return SerializableFunction(case_users_filter,
                                    users=self._get_filtered_users(),
                                    groups=case_sharing_groups)

    def format_export_data(self, export):
        from corehq.apps.export.views import EditCustomCaseExportView
        return {
            'export_id': export.get_id,
            'export_type': 'case',
            'name': export.name,
            'edit_url': reverse(EditCustomCaseExportView.urlname,
                                args=(self.domain, export.get_id)),
        }
