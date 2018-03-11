from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import timedelta
import dateutil
from django import forms
from django.urls import reverse
from django.utils.translation import ugettext as _, ugettext_lazy
from unidecode import unidecode

from corehq.apps.export.filters import (
    ReceivedOnRangeFilter,
    GroupFormSubmittedByFilter,
    OR, OwnerFilter, LastModifiedByFilter, UserTypeFilter,
    ModifiedOnRangeFilter, FormSubmittedByFilter, NOT, SmsReceivedRangeFilter
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.dbaccessors import (
    user_ids_at_locations_and_descendants, user_ids_at_locations
)
from corehq.apps.export.models.new import (
    DatePeriod,
    CaseExportInstance,
    FormExportInstanceFilters,
    CaseExportInstanceFilters,
)
from corehq.apps.reports.filters.case_list import CaseListFilter, CaseListFilterUtils
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter, EmwfUtils
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
from corehq.apps.hqwebapp.crispy import B3MultiField, CrispyTemplate
from corehq.apps.hqwebapp.widgets import (
    Select2MultipleChoiceWidget,
    DateRangePickerWidget,
    Select2,
    Select2Ajax,
)
from corehq.pillows import utils
from couchexport.util import SerializableFunction

from crispy_forms.bootstrap import InlineField
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from crispy_forms.layout import Layout
from dimagi.utils.dates import DateSpan

from corehq.util import flatten_non_iterable_list


class UserTypesField(forms.MultipleChoiceField):
    _USER_MOBILE = 'mobile'
    _USER_DEMO = 'demo_user'
    _USER_UNKNOWN = 'unknown'
    _USER_SUPPLY = 'supply'

    _USER_TYPES_CHOICES = [
        (_USER_MOBILE, ugettext_lazy("All Mobile Workers")),
        (_USER_DEMO, ugettext_lazy("Demo User")),
        (_USER_UNKNOWN, ugettext_lazy("Unknown Users")),
        (_USER_SUPPLY, ugettext_lazy("CommCare Supply")),
    ]

    widget = Select2MultipleChoiceWidget

    def __init__(self, *args, **kwargs):
        if len(args) == 0 and "choices" not in kwargs:  # choices is the first arg, and a kwarg
            kwargs['choices'] = self._USER_TYPES_CHOICES
        super(UserTypesField, self).__init__(*args, **kwargs)

    def clean(self, value):
        """
        Return a list of elastic search user types (each item in the return list
        is in corehq.pillows.utils.USER_TYPES) corresponding to the selected
        export user types.
        """
        es_user_types = []
        export_user_types = super(UserTypesField, self).clean(value)
        export_to_es_user_types_map = {
            self._USER_MOBILE: [utils.MOBILE_USER_TYPE],
            self._USER_DEMO: [utils.DEMO_USER_TYPE],
            self._USER_UNKNOWN: [
                utils.UNKNOWN_USER_TYPE, utils.SYSTEM_USER_TYPE, utils.WEB_USER_TYPE
            ],
            self._USER_SUPPLY: [utils.COMMCARE_SUPPLY_USER_TYPE]
        }
        for type_ in export_user_types:
            es_user_types.extend(export_to_es_user_types_map[type_])
        return es_user_types


class DateSpanField(forms.CharField):
    widget = DateRangePickerWidget

    def clean(self, value):
        date_range = super(DateSpanField, self).clean(value)
        dates = date_range.split(DateRangePickerWidget.separator)
        startdate = dateutil.parser.parse(dates[0])
        enddate = dateutil.parser.parse(dates[1])
        return DateSpan(startdate, enddate)


class CreateExportTagForm(forms.Form):
    # common fields
    model_type = forms.ChoiceField(
        choices=[
            ("", ugettext_lazy("Select model type")),
            ('case', ugettext_lazy('case')),
            ('form', ugettext_lazy('form')),
        ]
    )
    app_type = forms.CharField()
    application = forms.CharField()

    # Form export fields
    module = forms.CharField(required=False)
    form = forms.CharField(required=False)

    # Case export fields
    case_type = forms.CharField(required=False)

    def __init__(self, has_form_export_permissions, has_case_export_permissions, *args, **kwargs):
        self.has_form_export_permissions = has_form_export_permissions
        self.has_case_export_permissions = has_case_export_permissions
        super(CreateExportTagForm, self).__init__(*args, **kwargs)

        # We shouldn't ever be showing this form if the user has neither permission
        assert self.has_case_export_permissions or self.has_form_export_permissions
        if not (self.has_case_export_permissions and self.has_form_export_permissions):
            model_field = self.fields['model_type']
            if self.has_form_export_permissions:
                model_field.initial = "form"
            if self.has_case_export_permissions:
                model_field.initial = 'case'

            model_field.widget.attrs['readonly'] = True
            model_field.widget.attrs['disabled'] = True

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-2'
        self.helper.field_class = 'col-sm-10'

        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'model_type',
                    placeholder=_('Select model type'),
                    ng_model='formData.model_type',
                    ng_change='resetForm()',
                    ng_required="true",
                ),
                ng_show="!staticModelType"
            ),
            crispy.Div(
                crispy.Div(
                    crispy.Field(
                        'app_type',
                        placeholder=_("Select Application Type"),
                        ng_model="formData.app_type",
                        ng_change="updateAppChoices()",
                        ng_required="true",
                    ),
                    ng_show="hasSpecialAppTypes || formData.model_type === 'case'",
                ),
                crispy.Field(
                    'application',
                    placeholder=_("Select Application"),
                    ng_model="formData.application",
                    ng_change="formData.model_type === 'case' ? updateCaseTypeChoices() : updateModuleChoices()",
                    ng_required="true",
                ),
                crispy.Div(  # Form export fields
                    crispy.Field(
                        'module',
                        placeholder=_("Select Menu"),
                        ng_model="formData.module",
                        ng_disabled="!formData.application",
                        ng_change="updateFormChoices()",
                        ng_required="formData.model_type === 'form'",
                    ),
                    crispy.Field(
                        'form',
                        placeholder=_("Select Form"),
                        ng_model="formData.form",
                        ng_disabled="!formData.module",
                        ng_required="formData.model_type === 'form'",
                    ),
                    ng_show="formData.model_type === 'form'"
                ),
                crispy.Div(  # Case export fields
                    crispy.Field(
                        'case_type',
                        placeholder=_("Select Case Type"),
                        ng_model="formData.case_type",
                        ng_disabled="!formData.application",
                        ng_required="formData.model_type === 'case'",
                    ),
                    ng_show="formData.model_type === 'case'",
                ),
                ng_show="formData.model_type"
            )
        )

    @property
    def has_form_permissions_only(self):
        return self.has_form_export_permissions and not self.has_case_export_permissions

    @property
    def has_case_permissions_only(self):
        return not self.has_form_export_permissions and self.has_case_export_permissions

    def clean_model_type(self):
        model_type = self.cleaned_data['model_type']
        if self.has_form_permissions_only:
            model_type = "form"
        elif self.has_case_permissions_only:
            model_type = "case"
        return model_type

    def clean(self):
        cleaned_data = super(CreateExportTagForm, self).clean()
        model_type = cleaned_data.get("model_type")

        if model_type == "form":
            # Require module and form fields if model_type is form
            errors = []
            if not cleaned_data.get("module"):
                errors.append(forms.ValidationError(_("Menu is required")))
            if not cleaned_data.get("form"):
                errors.append(forms.ValidationError(_("Form is required")))
            if errors:
                raise forms.ValidationError(errors)
        elif model_type == "case":
            # Require case_type if model_type is case
            if not cleaned_data.get('case_type'):
                raise forms.ValidationError(_("case type is required"))


class BaseFilterExportDownloadForm(forms.Form):
    _export_type = 'all'  # should be form or case

    _USER_MOBILE = 'mobile'
    _USER_DEMO = 'demo_user'
    _USER_UNKNOWN = 'unknown'
    _USER_SUPPLY = 'supply'
    _USER_ADMIN = 'admin'

    _USER_TYPES_CHOICES = [
        (_USER_MOBILE, ugettext_lazy("All Mobile Workers")),
        (_USER_DEMO, ugettext_lazy("Demo User")),
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
    user_types = UserTypesField(
        label=ugettext_lazy("Select User Types"),
        required=False,
    )
    group = forms.ChoiceField(
        label=ugettext_lazy("Select Group"),
        required=False,
        widget=Select2()
    )

    _EXPORT_TO_ES_USER_TYPES_MAP = {
        _USER_MOBILE: [utils.MOBILE_USER_TYPE],
        _USER_DEMO: [utils.DEMO_USER_TYPE],
        _USER_UNKNOWN: [
            utils.UNKNOWN_USER_TYPE, utils.SYSTEM_USER_TYPE, utils.WEB_USER_TYPE
        ],
        _USER_SUPPLY: [utils.COMMCARE_SUPPLY_USER_TYPE]
    }

    # To be used by subclasses when rendering their own layouts using filters and extra_fields
    skip_layout = False

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        super(BaseFilterExportDownloadForm, self).__init__(*args, **kwargs)

        self.fields['group'].choices = [("", "")] + [(g._id, g.name) for g in Group.get_reporting_groups(self.domain_object.name)]

        if not self.domain_object.uses_locations:
            # don't use CommCare Supply as a user_types choice if the domain
            # is not a CommCare Supply domain.
            self.fields['user_types'].choices = self.fields['user_types'].choices[:-1]

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3'
        self.helper.field_class = 'col-sm-5'
        if not self.skip_layout:
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
            # The following line results in all users who match the
            # HQUserType.ADMIN filter to be included if the unknown users
            # filter is selected.
            self._USER_UNKNOWN in user_types,
            self._USER_UNKNOWN in user_types,
            self._USER_SUPPLY in user_types
        ]
        # todo refactor HQUserType
        user_filters = HQUserType._get_manual_filterset(
            (True,) * HQUserType.count,
            user_filter_toggles
        )
        return users_matching_filter(self.domain_object.name, user_filters)

    def _get_selected_user_types(self, mobile_user_and_groups_slugs=None):
        return self.cleaned_data['user_types']

    def _get_es_user_types(self, mobile_user_and_groups_slugs=None):
        """
        Return a list of elastic search user types (each item in the return list
        is in corehq.pillows.utils.USER_TYPES) corresponding to the selected
        export user types.
        """
        es_user_types = []
        export_user_types = self._get_selected_user_types(mobile_user_and_groups_slugs)
        export_to_es_user_types_map = self._EXPORT_TO_ES_USER_TYPES_MAP
        for type_ in export_user_types:
            es_user_types.extend(export_to_es_user_types_map[type_])
        return es_user_types

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
            'has_case_history_table': export.has_case_history_table if self._export_type == 'case' else None
        }


def _date_help_text(field):
    return """
        <small class="label label-default">{fmt}</small>
        <div ng-show="feedFiltersForm.{field}.$invalid && !feedFiltersForm.{field}.$pristine" class="help-block">
            {msg}
        </div>
    """.format(
        field=field,
        fmt=ugettext_lazy("YYYY-MM-DD"),
        msg=ugettext_lazy("Invalid date format"),
    )


class DashboardFeedFilterForm(forms.Form):
    """
    A form used to configure the filters on a Dashboard Feed export
    """
    emwf_case_filter = forms.Field(
        label=ugettext_lazy("Groups or Users"),
        required=False,
        widget=Select2Ajax(multiple=True),
    )
    emwf_form_filter = forms.Field(
        label=ugettext_lazy("Groups or Users"),
        required=False,
        widget=Select2Ajax(multiple=True),
    )
    date_range = forms.ChoiceField(
        label=ugettext_lazy("Date Range"),
        required=True,
        initial="last7",
        choices=[
            ("last7", ugettext_lazy("Last 7 days")),
            ("last30", ugettext_lazy("Last 30 days")),
            ("lastmonth", ugettext_lazy("Last month")),
            ("lastyear", ugettext_lazy("Last year")),
            ("lastn", ugettext_lazy("Days ago")),
            ("since", ugettext_lazy("Since a date")),
            ("range", ugettext_lazy("From a date to a date")),
        ],
    )
    days = forms.IntegerField(
        label=ugettext_lazy("Number of Days"),
        required=False,
    )
    start_date = forms.DateField(
        label=ugettext_lazy("Begin Date"),
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"placeholder": "YYYY-MM-DD", "ng-pattern": "dateRegex"}),
        help_text=_date_help_text("start_date")
    )
    end_date = forms.DateField(
        label=ugettext_lazy("End Date"),
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"placeholder": "YYYY-MM-DD", "ng-pattern": "dateRegex"}),
        help_text=_date_help_text("end_date"),
    )

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        super(DashboardFeedFilterForm, self).__init__(*args, **kwargs)

        self.fields['emwf_case_filter'].widget.set_url(
            reverse(CaseListFilter.options_url, args=(self.domain_object.name,))
        )
        self.fields['emwf_form_filter'].widget.set_url(
            reverse(ExpandedMobileWorkerFilter.options_url, args=(self.domain_object.name,))
        )

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-10 col-lg-10'
        self.helper.layout = Layout(*self.layout_fields)

    def clean(self):
        cleaned_data = super(DashboardFeedFilterForm, self).clean()
        errors = []

        if cleaned_data['emwf_form_filter'] and cleaned_data['emwf_case_filter']:
            # This should only happen if a user builds the reqest manually or there is an error rendering the form
            forms.ValidationError(_("Cannot submit case and form users and groups filter"))

        date_range = cleaned_data['date_range']
        if date_range in ("since", "range") and not cleaned_data.get('start_date', None):
            errors.append(
                forms.ValidationError(_("A valid start date is required"))
            )
        if date_range == "range" and not cleaned_data.get('end_date', None):
            errors.append(
                forms.ValidationError(_("A valid end date is required"))
            )
        if errors:
            raise forms.ValidationError(errors)

    def format_export_data(self, export):
        return {
            'domain': self.domain_object.name,
            'sheet_name': export.name,
            'export_id': export.get_id,
            'export_type': self._export_type,
            'name': export.name,
            'edit_url': self.get_edit_url(export),
        }

    @property
    def layout_fields(self):
        return [
            crispy.Div(
                crispy.Field(
                    'emwf_case_filter',
                    # ng_model='formData.emwf_case_filter',
                    # ng_model_options="{ getterSetter: true }",
                ),
                ng_show="modelType === 'case'"
            ),
            crispy.Div(
                crispy.Field(
                    'emwf_form_filter',
                    # ng_model='formData.emwf_form_filter',
                    # ng_model_options="{ getterSetter: true }",
                ),
                ng_show="modelType === 'form'"
            ),
            crispy.Field(
                'date_range',
                ng_model='formData.date_range',
                ng_required='true',
            ),
            crispy.Div(
                crispy.Field("days", ng_model="formData.days"),
                ng_show="formData.date_range === 'lastn'"
            ),
            crispy.Div(
                crispy.Field(
                    "start_date",
                    ng_model="formData.start_date",
                    ng_required="formData.date_range === 'since' || formData.date_range === 'range'"
                ),
                ng_show="formData.date_range === 'range' || formData.date_range === 'since'",
                ng_class=
                    "{'has-error': feedFiltersForm.start_date.$invalid && !feedFiltersForm.start_date.$pristine}",
            ),
            crispy.Div(
                crispy.Field(
                    "end_date",
                    ng_model="formData.end_date",
                    ng_required="formData.date_range === 'range'"
                ),
                ng_show="formData.date_range === 'range'",
                ng_class="{'has-error': feedFiltersForm.end_date.$invalid && !feedFiltersForm.end_date.$pristine}",
            )
        ]

    def to_export_instance_filters(self, can_access_all_locations, accessible_location_ids):
        """
        Serialize the bound form as an ExportInstanceFilters object.
        """
        # Confirm that either form filter data or case filter data but not both has been submitted.
        assert (
            (self.cleaned_data['emwf_form_filter'] is not None) !=
            (self.cleaned_data['emwf_case_filter'] is not None)
        )
        if self.cleaned_data['emwf_form_filter']:
            # It's a form export
            return self._to_form_export_instance_filters(can_access_all_locations, accessible_location_ids)
        else:
            # it's a case export
            return self._to_case_export_instance_filters(can_access_all_locations, accessible_location_ids)

    def _to_case_export_instance_filters(self, can_access_all_locations, accessible_location_ids):
        emwf_selections = [x['id'] for x in self.cleaned_data["emwf_case_filter"]]

        return CaseExportInstanceFilters(
            date_period=DatePeriod(
                period_type=self.cleaned_data['date_range'],
                days=self.cleaned_data['days'],
                begin=self.cleaned_data['start_date'],
                end=self.cleaned_data['end_date'],
            ),
            users=CaseListFilter.selected_user_ids(emwf_selections),
            reporting_groups=CaseListFilter.selected_reporting_group_ids(emwf_selections),
            locations=CaseListFilter.selected_location_ids(emwf_selections),
            user_types=CaseListFilter.selected_user_types(emwf_selections),
            can_access_all_locations=can_access_all_locations,
            accessible_location_ids=accessible_location_ids,
            sharing_groups=CaseListFilter.selected_sharing_group_ids(emwf_selections),
            show_all_data=CaseListFilter.show_all_data(emwf_selections),
            show_project_data=CaseListFilter.show_project_data(emwf_selections),
        )

    def _to_form_export_instance_filters(self, can_access_all_locations, accessible_location_ids):
        emwf_selections = [x['id'] for x in self.cleaned_data["emwf_form_filter"]]

        return FormExportInstanceFilters(
            date_period=DatePeriod(
                period_type=self.cleaned_data['date_range'],
                days=self.cleaned_data['days'],
                begin=self.cleaned_data['start_date'],
                end=self.cleaned_data['end_date'],
            ),
            users=ExpandedMobileWorkerFilter.selected_user_ids(emwf_selections),
            reporting_groups=ExpandedMobileWorkerFilter.selected_reporting_group_ids(emwf_selections),
            locations=ExpandedMobileWorkerFilter.selected_location_ids(emwf_selections),
            user_types=ExpandedMobileWorkerFilter.selected_user_types(emwf_selections),
            can_access_all_locations=can_access_all_locations,
            accessible_location_ids=accessible_location_ids,
        )

    @classmethod
    def get_form_data_from_export_instance_filters(cls, export_instance_filters, domain, export_type):
        """
        Return a dictionary representing the form data from a given ExportInstanceFilters.
        This is used to populate a form from an existing export instance
        :param export_instance_filters:
        :return:
        """
        if export_instance_filters:
            date_period = export_instance_filters.date_period
            selected_items = (
                export_instance_filters.users +
                export_instance_filters.reporting_groups +
                export_instance_filters.locations +
                export_instance_filters.user_types
            )
            if isinstance(export_instance_filters, CaseExportInstanceFilters):
                selected_items += (
                    export_instance_filters.sharing_groups +
                    (["all_data"] if export_instance_filters.show_all_data else []) +
                    (["project_data"] if export_instance_filters.show_project_data else [])
                )

            emwf_utils_class = CaseListFilterUtils if export_type is CaseExportInstance else EmwfUtils
            emwf_data = []
            for item in selected_items:
                choice_tuple = emwf_utils_class(domain).id_to_choice_tuple(str(item))
                if choice_tuple:
                    emwf_data.append({"id": choice_tuple[0], "text": choice_tuple[1]})

            return {
                "date_range": date_period.period_type if date_period else None,
                "days": date_period.days if date_period else None,
                "start_date": date_period.begin if date_period else None,
                "end_date": date_period.end if date_period else None,
                "emwf_form_filter": emwf_data,
                "emwf_case_filter": emwf_data,
            }
        else:
            return None


class GenericFilterFormExportDownloadForm(BaseFilterExportDownloadForm):
    """The filters for Form Export Download
    """
    _export_type = 'form'

    date_range = DateSpanField(
        label=ugettext_lazy("Date Range"),
        required=True,
    )

    def __init__(self, domain_object, timezone, *args, **kwargs):
        self.timezone = timezone
        super(GenericFilterFormExportDownloadForm, self).__init__(domain_object, *args, **kwargs)

        self.fields['date_range'].help_text = _(
            "Filters forms by date received. The timezone for this export is %(timezone)s."
        ) % {
            'timezone': self.timezone,
        }

        # update date_range filter's initial values to span the entirety of
        # the domain's submission range
        default_datespan = datespan_from_beginning(self.domain_object, self.timezone)
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

    def get_form_filter(self):
        raise NotImplementedError

    def get_multimedia_task_kwargs(self, export, download_id, mobile_user_and_group_slugs=None):
        """These are the kwargs for the Multimedia Download task,
        specific only to forms.
        """
        datespan = self.cleaned_data['date_range']
        return {
            'domain': self.domain_object.name,
            'startdate': datespan.startdate.isoformat(),
            'enddate': (datespan.enddate + timedelta(days=1)).isoformat(),
            'app_id': export.app_id,
            'xmlns': export.xmlns if hasattr(export, 'xmlns') else '',
            'export_id': export.get_id,
            'zip_name': 'multimedia-{}'.format(unidecode(export.name)),
            'user_types': self._get_es_user_types(mobile_user_and_group_slugs),
            'group': self.data['group'],
            'download_id': download_id
        }

    def format_export_data(self, export):
        export_data = super(GenericFilterFormExportDownloadForm, self).format_export_data(export)
        export_data.update({
            'xmlns': export.xmlns if hasattr(export, 'xmlns') else '',
        })
        return export_data


class FilterFormCouchExportDownloadForm(GenericFilterFormExportDownloadForm):
    # This class will be removed when the switch over to ES exports is complete

    def get_edit_url(self, export):
        from corehq.apps.export.views import EditCustomFormExportView
        return reverse(EditCustomFormExportView.urlname,
                       args=(self.domain_object.name, export.get_id))

    def get_form_filter(self):
        form_filter = SerializableFunction(app_export_filter, app_id=None)
        datespan_filter = self._get_datespan_filter()
        if datespan_filter:
            form_filter &= datespan_filter
        form_filter &= self._get_user_or_group_filter()
        return form_filter

    def _get_user_or_group_filter(self):
        group = self._get_group()
        if group:
            # filter by groups
            return SerializableFunction(group_filter, group=group)
        # filter by users
        return SerializableFunction(users_filter,
                                    users=self._get_filtered_users())

    def _get_datespan_filter(self):
        datespan = self.cleaned_data['date_range']
        if datespan.is_valid():
            datespan.set_timezone(self.timezone)
            return SerializableFunction(datespan_export_filter,
                                        datespan=datespan)

    def get_multimedia_task_kwargs(self, export, download_id, mobile_user_and_group_slugs=None):
        kwargs = super(FilterFormCouchExportDownloadForm, self).get_multimedia_task_kwargs(export, download_id)
        kwargs['export_is_legacy'] = True
        return kwargs


class EmwfFilterExportMixin(object):
    # filter to be used to identify objects(forms/cases) for users
    export_user_filter = FormSubmittedByFilter

    # filter class for including dynamic fields in the context of the view as dynamic_filters
    dynamic_filter_class = ExpandedMobileWorkerFilter

    def _get_user_ids(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['l__e80c5e54ab552245457d2546d0cdbb05']
        :return: ['e80c5e54ab552245457d2546d0cdbb05']
        """
        return self.dynamic_filter_class.selected_user_ids(mobile_user_and_group_slugs)

    def _get_locations_ids(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['l__e80c5e54ab552245457d2546d0cdbb05']
        :return: ['e80c5e54ab552245457d2546d0cdbb05']
        """
        return self.dynamic_filter_class.selected_location_ids(mobile_user_and_group_slugs)

    def _get_group_ids(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['g__e80c5e54ab552245457d2546d0cdbb05']
        :return: ['e80c5e54ab552245457d2546d0cdbb05']
        """
        return self.dynamic_filter_class.selected_group_ids(mobile_user_and_group_slugs)

    def _get_selected_es_user_types(self, mobile_user_and_group_slugs):
        """
        :param: ['t__0', 't__1']
        :return: int values corresponding to user types as in HQUserType
        HQUserType user_type_mapping to be used for mapping
        """
        return self.dynamic_filter_class.selected_user_types(mobile_user_and_group_slugs)


class AbstractExportFilterBuilder(object):
    date_filter_class = None

    def __init__(self, domain_object, timezone):
        self.domain_object = domain_object
        self.timezone = timezone

    def get_user_ids_for_user_types(self, admin, unknown, demo, commtrack):
        """
        referenced from CaseListMixin to fetch user_ids for selected user type
        :param admin: if admin users to be included
        :param unknown: if unknown users to be included
        :param demo: if demo users to be included
        :param commtrack: if commtrack users to be included
        :return: user_ids for selected user types
        """
        from corehq.apps.es import filters, users as user_es
        if not any([admin, unknown, demo]):
            return []

        user_filters = [filter_ for include, filter_ in [
            (admin, user_es.admin_users()),
            (unknown, filters.OR(user_es.unknown_users(), user_es.web_users())),
            (demo, user_es.demo_users()),
        ] if include]

        query = (user_es.UserES()
                 .domain(self.domain_object.name)
                 .OR(*user_filters)
                 .show_inactive()
                 .remove_default_filter('not_deleted')
                 .fields([]))
        user_ids = query.run().doc_ids

        if commtrack:
            user_ids.append("commtrack-system")
        if demo:
            user_ids.append("demo_user_group_id")
            user_ids.append("demo_user")
        return user_ids

    def _get_users_filter(self, user_ids):
        """
        :return: User filter set by inheriting class
        """
        if user_ids:
            return self.export_user_filter(list(user_ids))

    def _get_datespan_filter(self, datespan):
        if datespan:
            try:
                if not datespan.is_valid():
                    return
                datespan.set_timezone(self.timezone)
            except AttributeError:
                # Some date_intervals (e.g. DatePeriod instances) don't have a set_timezone() or is_valid()
                # methods.
                pass
            return self.date_filter_class(gte=datespan.startdate, lt=datespan.enddate + timedelta(days=1))

    def _get_locations_filter(self, location_ids):
        """
        :return: User filter with users at filtered locations and their descendants
        """
        if location_ids:
            user_ids = user_ids_at_locations_and_descendants(location_ids)
            return self.export_user_filter(user_ids)


class FormExportFilterBuilder(AbstractExportFilterBuilder):
    export_user_filter = FormSubmittedByFilter
    date_filter_class = ReceivedOnRangeFilter

    def _get_group_filter(self, group_ids):
        if group_ids:
            return GroupFormSubmittedByFilter(list(group_ids))

    def _get_user_type_filter(self, user_types):
        """
        :return: FormSubmittedByFilter with user_ids for selected user types
        """
        if user_types:
            form_filters = []
            if HQUserType.REGISTERED in user_types:
                # TODO: This
                form_filters.append(UserTypeFilter(BaseFilterExportDownloadForm._USER_MOBILE))
            user_ids = self.get_user_ids_for_user_types(
                admin=HQUserType.ADMIN in user_types,
                unknown=HQUserType.UNKNOWN in user_types,
                demo=HQUserType.DEMO_USER in user_types,
                commtrack=False,
            )
            form_filters.append(FormSubmittedByFilter(user_ids))
            return form_filters

    def get_filters(self, can_access_all_locations, accessible_location_ids, group_ids, user_types, user_ids,
                   location_ids, date_range):
        """
        Return a list of `ExportFilter`s for the given ids.
        This list of filters will eventually be ANDed to filter the documents that appear in the export.
        Therefore, the filter will be constructed as such:
            (groups OR user type OR users OR locations) AND date filter AND accessible locations

        :param can_access_all_locations: True if there are no user based location restrictions
        :param accessible_location_ids: If not can_access_all_locations, this is a list of location ids that the
            user is restricted to seeing data from
        :param group_ids:
        :param user_types:
        :param user_ids:
        :param location_ids:
        :param date_range: A DatePeriod or DateSpan
        """
        form_filters = []
        if can_access_all_locations:
            form_filters += [_f for _f in [
                self._get_group_filter(group_ids),
                self._get_user_type_filter(user_types),
            ] if _f]

        form_filters += [_f for _f in [
            self._get_users_filter(user_ids),
            self._get_locations_filter(location_ids)
        ] if _f]

        form_filters = flatten_non_iterable_list(form_filters)
        if form_filters:
            form_filters = [OR(*form_filters)]
        else:
            form_filters = []
        date_filter = self._get_datespan_filter(date_range)
        if date_filter:
            form_filters.append(date_filter)
        if not can_access_all_locations:
            form_filters.append(self._scope_filter(accessible_location_ids))
        return form_filters

    def _scope_filter(self, accessible_location_ids):
        # Filter to be applied in AND with filters for export for restricted user
        # Restricts to forms submitted by users at accessible locations
        accessible_user_ids = user_ids_at_locations(list(accessible_location_ids))
        return FormSubmittedByFilter(accessible_user_ids)


class CaseExportFilterBuilder(AbstractExportFilterBuilder):
    export_user_filter = OwnerFilter
    date_filter_class = ModifiedOnRangeFilter

    def get_filters(self, can_access_all_locations, accessible_location_ids, show_all_data, show_project_data,
                   selected_user_types, datespan, group_ids, location_ids, user_ids):
        """
        Return a list of `ExportFilter`s for the given ids.
        This list of filters will eventually be ANDed to filter the documents that appear in the export.
        Therefore, the filter will be constructed as such:
            (groups OR user type OR users OR locations) AND date filter AND accessible locations

        :param can_access_all_locations: if request user has full organization access permission
        :param accessible_location_ids: If not can_access_all_locations, this is a list of location ids that the
            user is restricted to seeing data from
        :return: list of filters
        """
        if can_access_all_locations and show_all_data:
            # if all data then just filter by date
            case_filter = []
        elif can_access_all_locations and show_project_data:
            # show projects data except user_ids for user types excluded
            user_types = selected_user_types
            ids_to_exclude = self.get_user_ids_for_user_types(
                admin=HQUserType.ADMIN not in user_types,
                unknown=HQUserType.UNKNOWN not in user_types,
                demo=HQUserType.DEMO_USER not in user_types,
                # this should be true since we are excluding
                commtrack=True,
            )
            case_filter = [NOT(OwnerFilter(ids_to_exclude))]
        else:
            case_filter = self._get_filters_from_slugs(
                can_access_all_locations, group_ids, selected_user_types, location_ids, user_ids
            )

        date_filter = self._get_datespan_filter(datespan)
        if date_filter:
            case_filter.append(date_filter)

        if not can_access_all_locations:
            case_filter.append(self._scope_filter(accessible_location_ids))

        return case_filter

    def _get_filters_from_slugs(self, can_access_all_locations, selected_group_ids, selected_user_types,
                                location_ids, user_ids):
        """
        for full organization access:
            for selected groups return group ids and groups user ids otherwise fetches case sharing groups and
            locations ids
        for restricted access:
            fetches case sharing location ids
        :return: set of filters using OwnerFilter and LastModifiedByFilter along with group independent filters
        """
        group_ids = None

        if can_access_all_locations:
            group_ids = selected_group_ids

        owner_filter_ids = []
        last_modified_filter_ids = []
        if group_ids:
            groups_static_user_ids = Group.get_static_user_ids_for_groups(group_ids)
            groups_static_user_ids = flatten_non_iterable_list(groups_static_user_ids)
            owner_filter_ids = group_ids + groups_static_user_ids
            last_modified_filter_ids = groups_static_user_ids

        return [OR(
            OwnerFilter(list(owner_filter_ids)),
            LastModifiedByFilter(last_modified_filter_ids),
            *self._get_group_independent_filters(
                can_access_all_locations, selected_user_types, location_ids, user_ids
            )
        )]

    def _get_group_independent_filters(self, can_access_all_locations, selected_user_types, location_ids,
                                       user_ids):
        # filters for location and users for both and user type in case of full access
        if can_access_all_locations:
            user_types = selected_user_types
            ids_to_include = self.get_user_ids_for_user_types(
                admin=HQUserType.ADMIN in user_types,
                unknown=HQUserType.UNKNOWN in user_types,
                demo=HQUserType.DEMO_USER in user_types,
                commtrack=False,
            )
            default_filters = [OwnerFilter(ids_to_include)]
        else:
            default_filters = []
        # filters for cases owned by users at selected locations and their descendants
        default_filters.append(self._get_locations_filter(location_ids))
        #default_filters.append(self.export_user_filter(location_ids))
        # filters for cases owned by selected locations and their descendants
        default_filters.append(
            self.export_user_filter(self._get_selected_locations_and_descendants_ids(location_ids))
        )

        default_filters.append(self._get_users_filter(list(user_ids)))
        default_filters.append(LastModifiedByFilter(list(user_ids)))
        return [_f for _f in default_filters if _f]

    def _get_selected_locations_and_descendants_ids(self, location_ids):
        return SQLLocation.objects.get_locations_and_children_ids(location_ids)

    def _scope_filter(self, accessible_location_ids):
        # Filter to be applied in AND with filters for export to add scope for restricted user
        # Restricts to cases owned by accessible locations and their respective users Or Cases
        # Last Modified by accessible users
        accessible_user_ids = user_ids_at_locations(list(accessible_location_ids))
        accessible_ids = accessible_user_ids + list(accessible_location_ids)
        return OR(OwnerFilter(accessible_ids), LastModifiedByFilter(accessible_user_ids))


class SmsExportFilterBuilder(AbstractExportFilterBuilder):
    date_filter_class = SmsReceivedRangeFilter

    def get_filters(self, datespan):
        return [self._get_datespan_filter(datespan)]


class EmwfFilterFormExport(EmwfFilterExportMixin, GenericFilterFormExportDownloadForm):
    """
    Generic Filter form including dynamic filters using ExpandedMobileWorkerFilter
    overrides few methods from GenericFilterFormExportDownloadForm for dynamic fields over form fields
    """
    export_user_filter = FormSubmittedByFilter
    dynamic_filter_class = ExpandedMobileWorkerFilter

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        self.skip_layout = True
        super(EmwfFilterFormExport, self).__init__(domain_object, *args, **kwargs)

        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-3'
        self.helper.layout = Layout(
            *super(EmwfFilterFormExport, self).extra_fields
        )

    def get_form_filter(self, mobile_user_and_group_slugs, can_access_all_locations, accessible_location_ids):
        """
        :param mobile_user_and_group_slugs: slug from request like
        ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04',
        'u__e80c5e54ab552245457d2546d0cdbb05', 't__1']
        :param can_access_all_locations: if request user has full organization access permission
        :return: set of form filters for export
        :filters:
        OR
            for full access:
                group's user ids via GroupFormSubmittedByFilter,
                users under user types,
                users by user_ids,
                users at locations and their descendants
            for restrict access:
                users by user_ids
                users at locations and their descendants
        AND
            datespan filter
        """
        filter_builder = FormExportFilterBuilder(self.domain_object, self.timezone)
        return filter_builder.get_filters(
            can_access_all_locations,
            accessible_location_ids,
            self._get_group_ids(mobile_user_and_group_slugs),
            self._get_selected_es_user_types(mobile_user_and_group_slugs),
            self._get_user_ids(mobile_user_and_group_slugs),
            self._get_locations_ids(mobile_user_and_group_slugs),
            self.cleaned_data['date_range'],
        )

    def _get_selected_user_types(self, mobile_user_and_group_slugs):
        return self._get_mapped_user_types(self._get_selected_es_user_types(mobile_user_and_group_slugs))

    def _get_mapped_user_types(self, selected_user_types):
        user_types = []
        if HQUserType.REGISTERED in selected_user_types:
            user_types.append(BaseFilterExportDownloadForm._USER_MOBILE)
        if HQUserType.ADMIN in selected_user_types:
            user_types.append(BaseFilterExportDownloadForm._USER_ADMIN)
        if HQUserType.UNKNOWN in selected_user_types:
            user_types.append(BaseFilterExportDownloadForm._USER_UNKNOWN)
        if HQUserType.DEMO_USER in selected_user_types:
            user_types.append(BaseFilterExportDownloadForm._USER_DEMO)

        return user_types

    def get_edit_url(self, export):
        from corehq.apps.export.views import EditNewCustomFormExportView
        return reverse(EditNewCustomFormExportView.urlname,
                       args=(self.domain_object.name, export._id))

    def get_multimedia_task_kwargs(self, export, download_id, mobile_user_and_group_slugs):
        kwargs = (super(EmwfFilterFormExport, self)
                  .get_multimedia_task_kwargs(export, download_id, mobile_user_and_group_slugs))
        kwargs['export_is_legacy'] = False
        return kwargs


class GenericFilterCaseExportDownloadForm(BaseFilterExportDownloadForm):
    def __init__(self, domain_object, timezone, *args, **kwargs):
        super(GenericFilterCaseExportDownloadForm, self).__init__(domain_object, *args, **kwargs)


class FilterCaseCouchExportDownloadForm(GenericFilterCaseExportDownloadForm):
    _export_type = 'case'
    # This class will be removed when the switch over to ES exports is complete

    def get_edit_url(self, export):
        from corehq.apps.export.views import EditCustomCaseExportView
        return reverse(EditCustomCaseExportView.urlname,
                       args=(self.domain_object.name, export.get_id))

    def get_case_filter(self):
        group = self._get_group()
        if group:
            return SerializableFunction(case_group_filter, group=group)
        case_sharing_groups = [g.get_id for g in
                               Group.get_case_sharing_groups(self.domain_object.name)]
        return SerializableFunction(case_users_filter,
                                    users=self._get_filtered_users(),
                                    groups=case_sharing_groups)


class FilterCaseESExportDownloadForm(EmwfFilterExportMixin, GenericFilterCaseExportDownloadForm):
    export_user_filter = OwnerFilter
    dynamic_filter_class = CaseListFilter

    _export_type = 'case'

    date_range = DateSpanField(
        label=ugettext_lazy("Date Range"),
        required=True,
        help_text="Export cases modified in this date range",
    )

    def __init__(self, domain_object, timezone, *args, **kwargs):
        self.timezone = timezone
        self.skip_layout = True
        super(FilterCaseESExportDownloadForm, self).__init__(domain_object, timezone, *args, **kwargs)

        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-3'
        # update date_range filter's initial values to span the entirety of
        # the domain's submission range
        default_datespan = datespan_from_beginning(self.domain_object, self.timezone)
        self.fields['date_range'].widget = DateRangePickerWidget(
            default_datespan=default_datespan
        )
        self.helper.layout = Layout(
            *self.extra_fields
        )

    def get_edit_url(self, export):
        from corehq.apps.export.views import EditNewCustomCaseExportView
        return reverse(EditNewCustomCaseExportView.urlname,
                       args=(self.domain_object.name, export.get_id))

    def get_case_filter(self, mobile_user_and_group_slugs, can_access_all_locations, accessible_location_ids):
        """
        Taking reference from CaseListMixin allow filters depending on locations access
        :param mobile_user_and_group_slugs: ['g__e80c5e54ab552245457d2546d0cdbb03', 't__0', 't__1']
        :param can_access_all_locations: if request user has full organization access permission
        :return: set of filters
        """
        filter_builder = CaseExportFilterBuilder(self.domain_object, self.timezone)
        return filter_builder.get_filters(
            can_access_all_locations,
            accessible_location_ids,
            self.dynamic_filter_class.show_all_data(mobile_user_and_group_slugs),
            self.dynamic_filter_class.show_project_data(mobile_user_and_group_slugs),
            self.dynamic_filter_class.selected_user_types(mobile_user_and_group_slugs),
            self.cleaned_data['date_range'],
            self._get_group_ids(mobile_user_and_group_slugs),
            self._get_locations_ids(mobile_user_and_group_slugs),
            self._get_user_ids(mobile_user_and_group_slugs),
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


class FilterSmsESExportDownloadForm(BaseFilterExportDownloadForm):
    date_range = DateSpanField(
        label=ugettext_lazy("Date Range"),
        required=True,
        help_text=ugettext_lazy("Export messages sent in this date range"),
    )

    def __init__(self, domain_object, timezone, *args, **kwargs):
        self.timezone = timezone
        self.skip_layout = True
        super(FilterSmsESExportDownloadForm, self).__init__(domain_object, *args, **kwargs)

        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-3'
        # update date_range filter's initial values to span the entirety of
        # the domain's submission range
        default_datespan = datespan_from_beginning(self.domain_object, self.timezone)
        self.fields['date_range'].widget = DateRangePickerWidget(
            default_datespan=default_datespan
        )
        self.helper.layout = Layout(
            *self.extra_fields
        )

    def get_edit_url(self, export):
        return None

    def get_filter(self):
        filter_builder = SmsExportFilterBuilder(self.domain_object, self.timezone)
        datespan = self.cleaned_data['date_range']
        return filter_builder.get_filters(datespan)

    @property
    def extra_fields(self):
        return [
            crispy.Field(
                'date_range',
                ng_model='formData.date_range',
                ng_required='true',
            ),
        ]
