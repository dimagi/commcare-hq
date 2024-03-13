import re
from datetime import timedelta

from django import forms
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

import dateutil
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms.bootstrap import StrictButton

from corehq import privileges
from dimagi.utils.dates import DateSpan

from corehq.apps.export.filters import (
    AND,
    NOT,
    OR,
    FormSubmittedByFilter,
    GroupFormSubmittedByFilter,
    LastModifiedByFilter,
    ModifiedOnRangeFilter,
    OwnerFilter,
    ReceivedOnRangeFilter,
    SmsReceivedRangeFilter,
    UserTypeFilter,
)
from corehq.apps.export.models.new import (
    CaseExportInstance,
    CaseExportInstanceFilters,
    DatePeriod,
    FormExportInstanceFilters,
)
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.crispy import HQFormHelper, HQModalFormHelper
from corehq.apps.hqwebapp.widgets import DateRangePickerWidget, Select2Ajax
from corehq.apps.locations.dbaccessors import (
    mobile_user_ids_at_locations,
    user_ids_at_locations_and_descendants,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.filters.case_list import (
    CaseListFilter,
    CaseListFilterUtils,
)
from corehq.apps.reports.filters.users import (
    EmwfUtils,
    ExpandedMobileWorkerFilter,
)
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.util import datespan_from_beginning
from corehq.toggles import FILTER_ON_GROUPS_AND_LOCATIONS
from corehq.util import flatten_non_iterable_list
from corehq.apps.userreports.dbaccessors import get_datasources_for_domain


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
            ("", gettext_lazy("Select model type")),
            ('case', gettext_lazy('case')),
            ('form', gettext_lazy('form')),
        ]
    )
    app_type = forms.CharField(widget=forms.Select(choices=[]))
    application = forms.CharField(required=False, widget=forms.Select(choices=[]))

    # Form export fields
    module = forms.CharField(required=False, widget=forms.Select(choices=[]))
    form = forms.CharField(required=False, widget=forms.Select(choices=[]))

    # Case export fields
    case_type = forms.CharField(required=False, widget=forms.Select(choices=[]))

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

        self.helper = HQModalFormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'model_type',
                    placeholder=_('Select model type'),
                    data_bind="value: modelType",
                ),
                data_bind="visible: !staticModelType",
            ),
            crispy.Div(
                crispy.Div(
                    crispy.Field(
                        'app_type',
                        placeholder=_("Select Application Type"),
                        data_bind="value: appType",
                    ),
                    data_bind="visible: showAppType()",
                ),
                crispy.Div(  # Form export fields
                    crispy.Field(
                        'application',
                        placeholder=_("Select Application"),
                        data_bind="value: application",
                    ),
                    crispy.Field(
                        'module',
                        placeholder=_("Select Menu"),
                        data_bind="value: module, disable: !application()",
                    ),
                    crispy.Field(
                        'form',
                        placeholder=_("Select Form"),
                        data_bind='''
                            value: form,
                            disable: !module(),
                        ''',
                    ),
                    data_bind="visible: isFormModel()",
                ),
                crispy.Div(  # Case export fields
                    crispy.Field(
                        'case_type',
                        placeholder=_("Select Case Type"),
                        data_bind="value: caseType",
                    ),
                    data_bind="visible: isCaseModel()",
                ),
                data_bind="visible: modelType()",
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
    _USER_WEB = 'web'
    _USER_UNKNOWN = 'unknown'
    _USER_SUPPLY = 'supply'
    _USER_ADMIN = 'admin'

    _USER_TYPES_CHOICES = [
        (_USER_MOBILE, gettext_lazy("All Mobile Workers")),
        (_USER_DEMO, gettext_lazy("Demo User")),
        (_USER_WEB, gettext_lazy("Web Users")),
        (_USER_UNKNOWN, gettext_lazy("Unknown Users")),
        (_USER_SUPPLY, gettext_lazy("CommCare Supply")),
    ]

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        super(BaseFilterExportDownloadForm, self).__init__(*args, **kwargs)

        self.helper = HQFormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            *self.extra_fields
        )

    @property
    def extra_fields(self):
        """
        :return: a list of extra crispy.Field classes as additional filters
        depending on type of export.
        """
        return []

    def get_edit_url(self, export):
        """Gets the edit url for the specified export.
        :param export: FormExportInstance instance or FormExportInstance instance
        :return: url to edit the export
        """
        raise NotImplementedError("must implement get_edit_url")

    def get_export_filters(self, request, data):
        '''
        This implementaion applies to forms and cases, which implement get_model_filter,
        but must be overridden for SMS exports.
        '''
        mobile_user_and_group_slugs = self.get_mobile_user_and_group_slugs(data)
        accessible_location_ids = None
        if not request.can_access_all_locations:
            accessible_location_ids = SQLLocation.active_objects.accessible_location_ids(
                self.domain_object.name, request.couch_user
            )
        return self.get_model_filter(
            mobile_user_and_group_slugs, request.can_access_all_locations, accessible_location_ids
        )

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

    def get_mobile_user_and_group_slugs(self, data):
        mobile_user_and_group_slugs_regex = re.compile(
            '(emw=|case_list_filter=|location_restricted_mobile_worker=){1}([^&]*)(&){0,1}'
        )
        matches = mobile_user_and_group_slugs_regex.findall(data[ExpandedMobileWorkerFilter.slug])
        return [n[1] for n in matches]


class DashboardFeedFilterForm(forms.Form):
    """
    A form used to configure the filters on a Dashboard Feed export
    """
    emwf_case_filter = forms.Field(
        label=gettext_lazy("Case Owner(s)"),
        required=False,
        widget=Select2Ajax(multiple=True),
        help_text=ExpandedMobileWorkerFilter.location_search_help,
    )
    emwf_form_filter = forms.Field(
        label=gettext_lazy("User(s)"),
        required=False,
        widget=Select2Ajax(multiple=True),
        help_text=ExpandedMobileWorkerFilter.location_search_help,
    )
    date_range = forms.ChoiceField(
        label=gettext_lazy("Date Range"),
        required=True,
        initial="last7",
        choices=[
            ("last7", gettext_lazy("Last 7 days")),
            ("last30", gettext_lazy("Last 30 days")),
            ("lastmonth", gettext_lazy("Last month")),
            ("lastyear", gettext_lazy("Last year")),
            ("lastn", gettext_lazy("Days ago")),
            ("since", gettext_lazy("Since a date")),
            ("range", gettext_lazy("From a date to a date")),
        ],
        help_text='''
            <span data-bind='visible: showEmwfFormFilter'>{}</span>
            <span data-bind='visible: showEmwfCaseFilter'>{}</span>
        '''.format(
            gettext_lazy("Export forms received in this date range."),
            gettext_lazy("Export cases modified in this date range."),
        )
    )
    days = forms.IntegerField(
        label=gettext_lazy("Number of Days"),
        required=False,
    )
    start_date = forms.DateField(
        label=gettext_lazy("Begin Date"),
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"placeholder": "YYYY-MM-DD"}),
        help_text="<small class='label label-default'>{}</small>".format(gettext_lazy("YYYY-MM-DD")),
    )
    end_date = forms.DateField(
        label=gettext_lazy("End Date"),
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"placeholder": "YYYY-MM-DD"}),
        help_text="<small class='label label-default'>{}</small>".format(gettext_lazy("YYYY-MM-DD")),
    )
    update_location_restriction = forms.BooleanField(
        label=gettext_lazy("Update location restriction to match filters."),
        required=False,
    )

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        self.can_user_access_all_locations = True
        if 'couch_user' in kwargs:
            couch_user = kwargs.pop('couch_user')
            self.can_user_access_all_locations = couch_user.has_permission(
                domain_object.name, 'access_all_locations'
            )
        super(DashboardFeedFilterForm, self).__init__(*args, **kwargs)

        self.can_restrict_access_by_location = domain_object.has_privilege(
            privileges.RESTRICT_ACCESS_BY_LOCATION
        )

        if not self.can_restrict_access_by_location or not self.can_user_access_all_locations:
            del self.fields['update_location_restriction']

        self.fields['emwf_case_filter'].widget.set_url(
            reverse(CaseListFilter.options_url, args=(self.domain_object.name,))
        )
        self.fields['emwf_form_filter'].widget.set_url(
            reverse(ExpandedMobileWorkerFilter.options_url, args=(self.domain_object.name,))
        )

        self.helper = HQModalFormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-10 col-lg-10'
        self.helper.layout = crispy.Layout(*self.layout_fields)

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
        fields = [
            crispy.Div(
                crispy.Field(
                    'emwf_case_filter',
                ),
                data_bind="visible: showEmwfCaseFilter",
            ),
            crispy.Div(
                crispy.Field(
                    'emwf_form_filter',
                ),
                data_bind="visible: showEmwfFormFilter",
            ),
            crispy.Field(
                'date_range',
                data_bind='value: dateRange',
            ),
            crispy.Div(
                crispy.Field("days", data_bind="value: days"),
                data_bind="visible: showDays",
            ),
            crispy.Div(
                crispy.Field(
                    "start_date",
                    data_bind="value: startDate",
                ),
                data_bind="visible: showStartDate, css: {'has-error': startDateHasError}",
            ),
            crispy.Div(
                crispy.Field(
                    "end_date",
                    data_bind="value: endDate",
                ),
                data_bind="visible: showEndDate, css: {'has-error': endDateHasError}",
            ),
        ]
        if self.can_restrict_access_by_location and self.can_user_access_all_locations:
            fields.append(crispy.Fieldset(
                _("Location Management"),
                crispy.Field(
                    'update_location_restriction',
                    data_bind='checked: updateLocationRestriction',
                ),
            ))
        return fields

    def to_export_instance_filters(self, can_access_all_locations, accessible_location_ids, export_type):
        """
        Serialize the bound form as an ExportInstanceFilters object.
        """
        # Confirm that either form filter data or case filter data but not both has been submitted.
        assert (
            (self.cleaned_data['emwf_form_filter'] is not None)
            != (self.cleaned_data['emwf_case_filter'] is not None)
        )
        assert (export_type == 'form' or export_type == 'case')
        if export_type == 'form':
            filters = self._to_form_export_instance_filters(can_access_all_locations, accessible_location_ids)
        else:
            filters = self._to_case_export_instance_filters(can_access_all_locations, accessible_location_ids)

        if (self.can_user_access_all_locations
                and self.can_restrict_access_by_location
                and self.cleaned_data['update_location_restriction']):
            filters.accessible_location_ids = filters.locations
            filters.can_access_all_locations = not filters.locations
        return filters

    def _to_case_export_instance_filters(self, can_access_all_locations, accessible_location_ids):
        emwf_selections = self.cleaned_data["emwf_case_filter"]

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
            show_all_data=CaseListFilter.show_all_data(emwf_selections)
            or CaseListFilter.no_filters_selected(emwf_selections),
            show_project_data=CaseListFilter.show_project_data(emwf_selections),
        )

    def _to_form_export_instance_filters(self, can_access_all_locations, accessible_location_ids):
        emwf_selections = self.cleaned_data["emwf_form_filter"]

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
                export_instance_filters.users
                + export_instance_filters.reporting_groups
                + export_instance_filters.locations
                + export_instance_filters.user_types
            )
            if isinstance(export_instance_filters, CaseExportInstanceFilters):
                selected_items += (
                    export_instance_filters.sharing_groups
                    + (["all_data"] if export_instance_filters.show_all_data else [])
                    + (["project_data"] if export_instance_filters.show_project_data else [])
                )

            emwf_utils_class = CaseListFilterUtils if export_type is CaseExportInstance else \
                EmwfUtils
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
        label=gettext_lazy("Date Range"),
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
                data_bind='value: dateRange',
            ),
        ]

    def format_export_data(self, export):
        export_data = super(GenericFilterFormExportDownloadForm, self).format_export_data(export)
        export_data.update({
            'xmlns': export.xmlns if hasattr(export, 'xmlns') else '',
        })
        return export_data


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

    def get_user_ids_for_user_types(self, admin, unknown, web, demo, commtrack, active=False, deactivated=False):
        """
        referenced from CaseListMixin to fetch user_ids for selected user type
        :param admin: if admin users to be included
        :param unknown: if unknown users to be included
        :param demo: if demo users to be included
        :param commtrack: if commtrack users to be included
        :return: user_ids for selected user types
        """
        from corehq.apps.es import filters, users as user_es
        if not any([admin, unknown, web, demo, commtrack, active, deactivated]):
            return []

        user_filters = [filter_ for include, filter_ in [
            (admin, user_es.admin_users()),
            (unknown, filters.OR(user_es.unknown_users())),
            (web, user_es.web_users()),
            (demo, user_es.demo_users()),
            # Sets the is_active filter status correctly for if either active or deactivated users are selected
            (active ^ deactivated, user_es.is_active(active)),
        ] if include]

        if not user_filters:
            return []

        query = (user_es.UserES()
                 .domain(self.domain_object.name)
                 .OR(*user_filters)
                 .remove_default_filter('not_deleted')
                 .remove_default_filter('active')
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

    def _get_user_type_filters(self, user_types):
        """
        :return: FormSubmittedByFilter with user_ids for selected user types
        """
        if user_types:
            form_filters = []
            # Select all mobile workers if both active and deactivated users are selected
            if HQUserType.ACTIVE in user_types and HQUserType.DEACTIVATED in user_types:
                form_filters.append(UserTypeFilter(BaseFilterExportDownloadForm._USER_MOBILE))
            user_ids = self.get_user_ids_for_user_types(
                admin=HQUserType.ADMIN in user_types,
                unknown=HQUserType.UNKNOWN in user_types,
                web=HQUserType.WEB in user_types,
                demo=HQUserType.DEMO_USER in user_types,
                commtrack=False,
                active=HQUserType.ACTIVE in user_types,
                deactivated=HQUserType.DEACTIVATED in user_types,
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

        form_filters = list(filter(None,
                                   [self._create_user_filter(user_types, user_ids, group_ids, location_ids)]))
        date_filter = self._get_datespan_filter(date_range)
        if date_filter:
            form_filters.append(date_filter)
        if not can_access_all_locations:
            show_inactive_users = HQUserType.DEACTIVATED in user_types
            form_filters.append(self._scope_filter(accessible_location_ids, show_inactive_users))

        return form_filters

    def _create_user_filter(self, user_types, user_ids, group_ids, location_ids):
        all_user_filters = None
        user_type_filters = self._get_user_type_filters(user_types)
        user_id_filter = self._get_users_filter(user_ids)
        group_filter = self._get_group_filter(group_ids)
        location_filter = self._get_locations_filter(location_ids)

        if not location_filter and not group_filter:
            group_and_location_metafilter = None
        elif FILTER_ON_GROUPS_AND_LOCATIONS.enabled(self.domain_object.name) and location_ids and group_ids:
            group_and_location_metafilter = AND(group_filter, location_filter)
        else:
            group_and_location_metafilter = OR(*list(filter(None, [group_filter, location_filter])))

        if group_and_location_metafilter or user_id_filter or user_type_filters:
            all_user_filter_list = [group_and_location_metafilter, user_id_filter]
            if user_type_filters:
                all_user_filter_list += user_type_filters
            all_user_filters = OR(*list(filter(None, all_user_filter_list)))

        return all_user_filters

    def _scope_filter(self, accessible_location_ids, include_inactive_users=False):
        # Filter to be applied in AND with filters for export for restricted user
        # Restricts to forms submitted by users at accessible locations
        accessible_user_ids = mobile_user_ids_at_locations(list(accessible_location_ids), include_inactive_users)
        return FormSubmittedByFilter(accessible_user_ids)


class CaseExportFilterBuilder(AbstractExportFilterBuilder):
    export_user_filter = OwnerFilter
    date_filter_class = ModifiedOnRangeFilter

    def get_filters(self, can_access_all_locations, accessible_location_ids, show_all_data, show_project_data,
                    show_deactivated_data, selected_user_types, datespan, group_ids, location_ids, user_ids):
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
        user_types = selected_user_types
        if can_access_all_locations and show_all_data:
            # if all data then just filter by date
            case_filter = []
        elif can_access_all_locations and show_project_data:
            # show projects data except user_ids for user types excluded
            ids_to_exclude = self.get_user_ids_for_user_types(
                admin=HQUserType.ADMIN not in user_types,
                unknown=HQUserType.UNKNOWN not in user_types,
                web=HQUserType.WEB in user_types,
                demo=HQUserType.DEMO_USER not in user_types,
                # this should be true since we are excluding
                commtrack=True,
            )
            case_filter = [NOT(OwnerFilter(ids_to_exclude))]
        elif can_access_all_locations and show_deactivated_data:
            # show projects data except user_ids for user types excluded
            ids_to_exclude = self.get_user_ids_for_user_types(
                admin=True,
                unknown=True,
                web=True,
                demo=True,
                commtrack=True,
                active=True,
                deactivated=False
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
                web=HQUserType.WEB in user_types,
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
        accessible_user_ids = mobile_user_ids_at_locations(list(accessible_location_ids))
        accessible_ids = accessible_user_ids + list(accessible_location_ids)
        return OR(OwnerFilter(accessible_ids), LastModifiedByFilter(accessible_user_ids))


class SmsExportFilterBuilder(AbstractExportFilterBuilder):
    date_filter_class = SmsReceivedRangeFilter

    def get_filters(self, datespan):
        return [self._get_datespan_filter(datespan)]


class EmwfFilterFormExport(EmwfFilterExportMixin, GenericFilterFormExportDownloadForm):
    """
    Generic Filter form including dynamic filters using ExpandedMobileWorkerFilters
    overrides few methods from GenericFilterFormExportDownloadForm for dynamic fields over form fields
    """
    export_user_filter = FormSubmittedByFilter
    dynamic_filter_class = ExpandedMobileWorkerFilter

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        super(EmwfFilterFormExport, self).__init__(domain_object, *args, **kwargs)

        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-3'

    def get_model_filter(self, mobile_user_and_group_slugs, can_access_all_locations, accessible_location_ids):
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

    def get_edit_url(self, export):
        from corehq.apps.export.views.edit import EditNewCustomFormExportView
        return reverse(EditNewCustomFormExportView.urlname,
                       args=(self.domain_object.name, export._id))


class FilterCaseESExportDownloadForm(EmwfFilterExportMixin, BaseFilterExportDownloadForm):
    export_user_filter = OwnerFilter
    dynamic_filter_class = CaseListFilter

    _export_type = 'case'

    date_range = DateSpanField(
        label=gettext_lazy("Date Range"),
        required=True,
        help_text=gettext_lazy("Export cases modified in this date range"),
    )

    def __init__(self, domain_object, timezone, *args, **kwargs):
        self.timezone = timezone
        super(FilterCaseESExportDownloadForm, self).__init__(domain_object, *args, **kwargs)

        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-3'
        # update date_range filter's initial values to span the entirety of
        # the domain's submission range
        default_datespan = datespan_from_beginning(self.domain_object, self.timezone)
        self.fields['date_range'].widget = DateRangePickerWidget(
            default_datespan=default_datespan
        )

    def get_edit_url(self, export):
        from corehq.apps.export.views.edit import EditNewCustomCaseExportView
        return reverse(EditNewCustomCaseExportView.urlname,
                       args=(self.domain_object.name, export.get_id))

    def get_model_filter(self, mobile_user_and_group_slugs, can_access_all_locations, accessible_location_ids):
        """
        Taking reference from CaseListMixin allow filters depending on locations access
        :param mobile_user_and_group_slugs: ['g__e80c5e54ab552245457d2546d0cdbb03', 't__0', 't__1']
        :param can_access_all_locations: if request user has full organization access permission
        :return: set of filters
        """
        filter_builder = CaseExportFilterBuilder(self.domain_object, self.timezone)
        show_all_data = self.dynamic_filter_class.show_all_data(mobile_user_and_group_slugs) or \
            self.dynamic_filter_class.no_filters_selected(mobile_user_and_group_slugs)
        return filter_builder.get_filters(
            can_access_all_locations,
            accessible_location_ids,
            show_all_data,
            self.dynamic_filter_class.show_project_data(mobile_user_and_group_slugs),
            self.dynamic_filter_class.show_deactivated_data(mobile_user_and_group_slugs),
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
                data_bind='value: dateRange',
            ),
        ]


class FilterSmsESExportDownloadForm(BaseFilterExportDownloadForm):
    date_range = DateSpanField(
        label=gettext_lazy("Date Range"),
        required=True,
        help_text=gettext_lazy("Export messages sent in this date range"),
    )

    def __init__(self, domain_object, timezone, *args, **kwargs):
        self.timezone = timezone
        super(FilterSmsESExportDownloadForm, self).__init__(domain_object, *args, **kwargs)

        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-3'
        # update date_range filter's initial values to span the entirety of
        # the domain's submission range
        default_datespan = datespan_from_beginning(self.domain_object, self.timezone)
        self.fields['date_range'].widget = DateRangePickerWidget(
            default_datespan=default_datespan
        )

    def get_edit_url(self, export):
        return None

    def get_filter(self):
        filter_builder = SmsExportFilterBuilder(self.domain_object, self.timezone)
        datespan = self.cleaned_data['date_range']
        return filter_builder.get_filters(datespan)

    def get_export_filters(self, request, data):
        return self.get_filter()

    @property
    def extra_fields(self):
        return [
            crispy.Field(
                'date_range',
                data_bind='value: dateRange',
            ),
        ]


class DatasourceExportDownloadForm(forms.Form):

    data_source = forms.ChoiceField(
        label=gettext_lazy("Select project data source"),
        required=True,
    )

    def __init__(self, domain, *args, **kwargs):
        super(DatasourceExportDownloadForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-3'

        self.fields['data_source'].choices = self.domain_datasources(domain)

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "",
                crispy.Div(
                    crispy.Field(
                        'data_source',
                        css_class='input-xlarge',
                        data_bind='value: dataSource'
                    ),
                    data_bind='visible: haveDatasources'
                ),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Download Data Export Tool query file"),
                    type="submit",
                    css_class="btn-primary",
                    data_bind="enable: haveDatasources"
                ),
            )
        )

    @staticmethod
    def domain_datasources(domain):
        return [
            (ds.data_source_id, ds.table_id)
            for ds in get_datasources_for_domain(domain)
        ]
