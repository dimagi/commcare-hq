import dateutil
from django import forms
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.groups.models import Group
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.util import (
    group_filter,
    users_matching_filter,
    users_filter,
    datespan_export_filter,
    app_export_filter,
    case_group_filter,
    case_users_filter,
    datespan_from_beginning,
)
from corehq.apps.style.crispy import B3MultiField, CrispyTemplate
from corehq.apps.style.forms.widgets import (
    Select2MultipleChoiceWidget,
    DateRangePickerWidget,
)
from couchexport.util import SerializableFunction

from crispy_forms.bootstrap import InlineField
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from crispy_forms.layout import Layout
from dimagi.utils.dates import DateSpan


class CreateFormExportTagForm(forms.Form):
    """The information necessary to create an export tag to begin creating a
    Form Export. This form interacts with CreateExportController in
    list_exports.ng.js
    """
    application = forms.CharField(required=False)
    module = forms.CharField(required=False)
    form = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super(CreateFormExportTagForm, self).__init__(*args, **kwargs)

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


class CreateCaseExportTagForm(forms.Form):
    """The information necessary to create an export tag to begin creating a
    Case Export. This form interacts with CreateExportController in
    list_exports.ng.js
    """
    application = forms.CharField(required=False)
    case_type = forms.CharField(
        required=False,
        help_text=mark_safe(
            '<span ng-show="!!hasNoCaseTypes '
            '&& !!createForm.application">{}</span>'.format(
                ugettext_noop(
                    """Note: This application does not appear to be using
<a href="https://wiki.commcarehq.org/display/commcarepublic/Case+Management">
case management</a>."""
                )
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super(CreateCaseExportTagForm, self).__init__(*args, **kwargs)

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
    _export_type = 'all'  # should be form or case

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
        default_datespan = datespan_from_beginning(self.domain, self.timezone)
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
        user_filter_toggles = [
            self._USER_MOBILE in user_types,
            self._USER_DEMO in user_types,
            self._USER_ADMIN in user_types,
            self._USER_UNKNOWN in user_types,
            self._USER_SUPPLY in user_types
        ]
        # todo refactor HQUserType
        user_filters = HQUserType._get_manual_filterset(
            (True,) * HQUserType.count,
            user_filter_toggles
        )
        return users_matching_filter(self.domain, user_filters)

    def _get_group(self):
        group = self.cleaned_data['group']
        if group:
            return Group.get(group)

    def get_edit_url(self, export):
        """Gets the edit url for the specified export.
        :param export: FormExportSchema instance or CaseExportSchema instance
        :return: url to edit the export
        """
        raise NotImplementedError("must implement get_edit_url")

    def format_export_data(self, export):
        return {
            'domain': self.domain,
            'sheet_name': export.name,
            'export_id': export.get_id,
            'export_type': self._export_type,
            'name': export.name,
            'edit_url': self.get_edit_url(export),
        }


class FilterFormExportDownloadForm(FilterExportDownloadForm):
    """The filters for Form Export Download
    """
    _export_type = 'form'

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
        dates = date_range.split(DateRangePickerWidget.separator)
        startdate = dateutil.parser.parse(dates[0])
        enddate = dateutil.parser.parse(dates[1])
        datespan = DateSpan(startdate, enddate)
        if datespan.is_valid():
            datespan.set_timezone(self.timezone)
            return SerializableFunction(datespan_export_filter,
                                        datespan=datespan)

    def get_form_filter(self):
        form_filter = SerializableFunction(app_export_filter, app_id=None)
        datespan_filter = self._get_datespan_filter()
        if datespan_filter:
            form_filter &= datespan_filter
        form_filter &= self._get_user_or_group_filter()
        return form_filter

    def get_edit_url(self, export):
        from corehq.apps.export.views import EditCustomFormExportView
        return reverse(EditCustomFormExportView.urlname,
                       args=(self.domain, export.get_id))

    def format_export_data(self, export):
        export_data = super(FilterFormExportDownloadForm, self).format_export_data(export)
        export_data.update({
            'xmlns': export.xmlns if hasattr(export, 'xmlns') else '',
        })
        return export_data


class FilterCaseExportDownloadForm(FilterExportDownloadForm):
    _export_type = 'case'

    def get_case_filter(self):
        group = self._get_group()
        if group:
            return SerializableFunction(case_group_filter, group=group)
        case_sharing_groups = [g.get_id for g in
                               Group.get_case_sharing_groups(self.domain)]
        return SerializableFunction(case_users_filter,
                                    users=self._get_filtered_users(),
                                    groups=case_sharing_groups)

    def get_edit_url(self, export):
        from corehq.apps.export.views import EditCustomCaseExportView
        return reverse(EditCustomCaseExportView.urlname,
                       args=(self.domain, export.get_id))
