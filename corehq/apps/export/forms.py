from datetime import timedelta
import dateutil
from django import forms
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _, ugettext_lazy
from unidecode import unidecode
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

from crispy_forms.layout import Layout
from dimagi.utils.dates import DateSpan


class CreateFormExportTagForm(forms.Form):
    """The information necessary to create an export tag to begin creating a
    Form Export. This form interacts with DrilldownToFormController in
    hq.app_data_drilldown.ng.js
    """
    app_type = forms.CharField()
    application = forms.CharField()
    module = forms.CharField()
    form = forms.CharField()

    def __init__(self, *args, **kwargs):
        super(CreateFormExportTagForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-2'
        self.helper.field_class = 'col-sm-10'

        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'app_type',
                    placeholder=_("Select Application Type"),
                    ng_model="formData.app_type",
                    ng_change="updateAppChoices()",
                    ng_required="true",
                ),
                ng_show="hasSpecialAppTypes",
            ),
            crispy.Field(
                'application',
                placeholder=_("Select Application"),
                ng_model="formData.application",
                ng_change="updateModuleChoices()",
                ng_required="true",
            ),
            crispy.Field(
                'module',
                placeholder=_("Select Module"),
                ng_model="formData.module",
                ng_disabled="!formData.application",
                ng_change="updateFormChoices()",
                ng_required="true",
            ),
            crispy.Field(
                'form',
                placeholder=_("Select Form"),
                ng_model="formData.form",
                ng_disabled="!formData.module",
                ng_required="true",
            ),
        )


class CreateCaseExportTagForm(forms.Form):
    """The information necessary to create an export tag to begin creating a
    Case Export. This form interacts with CreateExportController in
    list_exports.ng.js
    """
    app_type = forms.CharField()
    application = forms.CharField()
    case_type = forms.CharField()

    def __init__(self, *args, **kwargs):
        super(CreateCaseExportTagForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-2'
        self.helper.field_class = 'col-sm-10'

        self.helper.layout = crispy.Layout(
            crispy.Field(
                'app_type',
                placeholder=_("Select Application Type"),
                ng_model="formData.app_type",
                ng_change="updateAppChoices()",
                ng_required="true",
            ),
            crispy.Field(
                'application',
                placeholder=_("Select Application"),
                ng_model="formData.application",
                ng_change="updateCaseTypeChoices()",
                ng_required="true",
            ),
            crispy.Field(
                'case_type',
                placeholder=_("Select Case Type"),
                ng_model="formData.case_type",
                ng_disabled="!formData.application",
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
        (_USER_MOBILE, ugettext_lazy("All Mobile Workers")),
        (_USER_DEMO, ugettext_lazy("Demo User")),
        (_USER_ADMIN, ugettext_lazy("Admin User")),
        (_USER_UNKNOWN, ugettext_lazy("Unknown Users")),
        (_USER_SUPPLY, ugettext_lazy("CommCare Supply")),
    ]
    type_or_group = forms.ChoiceField(
        label=ugettext_lazy("User Types or Group"),
        required=False,
        choices=(
            ('type', ugettext_lazy("User Types")),
            ('group', ugettext_lazy("Group")),
        )
    )
    user_types = forms.MultipleChoiceField(
        label=ugettext_lazy("Select User Types"),
        widget=Select2MultipleChoiceWidget,
        choices=_USER_TYPES_CHOICES,
        required=False,
    )
    group = forms.CharField(
        label=ugettext_lazy("Select Group"),
        required=False,
    )

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        super(FilterExportDownloadForm, self).__init__(*args, **kwargs)

        if not self.domain_object.uses_locations:
            # don't use CommCare Supply as a user_types choice if the domain
            # is not a CommCare Supply domain.
            self.fields['user_types'].choices = self._USER_TYPES_CHOICES[:-1]

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
                        'domain': self.domain_object.name,
                    }),
                ),
                ng_show="formData.type_or_group === 'group'",
            ),
            *self.extra_fields
        )

    @property
    def extra_fields(self):
        """
        :return: a list of extra crispy.Field classes as additional filters
        depending on type of export.
        """
        return []

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
        return users_matching_filter(self.domain_object.name, user_filters)

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
            'domain': self.domain_object.name,
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

    date_range = forms.CharField(
        label=ugettext_lazy("Date Range"),
        required=True,
        widget=DateRangePickerWidget(),
    )

    def __init__(self, domain_object, timezone, *args, **kwargs):
        self.timezone = timezone
        super(FilterFormExportDownloadForm, self).__init__(domain_object, *args, **kwargs)

        self.fields['date_range'].help_text = _(
            "The timezone for this export is %(timezone)s."
        ) % {
            'timezone': self.timezone,
        }

        # update date_range filter's initial values to span the entirety of
        # the domain's submission range
        default_datespan = datespan_from_beginning(self.domain_object.name, self.timezone)
        self.fields['date_range'].widget = DateRangePickerWidget(
            default_datespan=default_datespan
        )

    @property
    def extra_fields(self):
        return [
            crispy.Field(
                'date_range',
                ng_model='formData.date_range',
                ng_required='true',
            ),
        ]

    def _get_user_or_group_filter(self):
        group = self._get_group()
        if group:
            # filter by groups
            return SerializableFunction(group_filter, group=group)
        # filter by users
        return SerializableFunction(users_filter,
                                    users=self._get_filtered_users())

    def _get_datespan_filter(self):
        datespan = self._get_datespan()
        if datespan.is_valid():
            datespan.set_timezone(self.timezone)
            return SerializableFunction(datespan_export_filter,
                                        datespan=datespan)

    def _get_datespan(self):
        date_range = self.cleaned_data['date_range']
        dates = date_range.split(DateRangePickerWidget.separator)
        startdate = dateutil.parser.parse(dates[0])
        enddate = dateutil.parser.parse(dates[1])
        return DateSpan(startdate, enddate)

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
                       args=(self.domain_object.name, export.get_id))

    def get_multimedia_task_kwargs(self, export, download_id):
        """These are the kwargs for the Multimedia Download task,
        specific only to forms.
        """
        datespan = self._get_datespan()
        return {
            'domain': self.domain_object.name,
            'startdate': datespan.startdate.isoformat(),
            'enddate': (datespan.enddate + timedelta(days=1)).isoformat(),
            'app_id': export.app_id,
            'xmlns': export.xmlns if hasattr(export, 'xmlns') else '',
            'export_id': export.get_id,
            'zip_name': 'multimedia-{}'.format(unidecode(export.name)),
            'download_id': download_id
        }

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
                               Group.get_case_sharing_groups(self.domain_object.name)]
        return SerializableFunction(case_users_filter,
                                    users=self._get_filtered_users(),
                                    groups=case_sharing_groups)

    def get_edit_url(self, export):
        from corehq.apps.export.views import EditCustomCaseExportView
        return reverse(EditCustomCaseExportView.urlname,
                       args=(self.domain_object.name, export.get_id))
