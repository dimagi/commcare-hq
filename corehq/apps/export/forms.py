from datetime import timedelta
import dateutil
from django import forms
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _, ugettext_lazy
from unidecode import unidecode

from corehq.apps.export.models.new import ExportInstanceFilters, DatePeriod
from corehq.apps.groups.models import Group

from corehq.apps.reports.util import (
    datespan_from_beginning,
)
from corehq.apps.style.crispy import B3MultiField, CrispyTemplate
from corehq.apps.style.forms.widgets import (
    Select2MultipleChoiceWidget,
    DateRangePickerWidget,
    Select2)

from crispy_forms.bootstrap import InlineField
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from crispy_forms.layout import Layout
from dimagi.utils.dates import DateSpan

USER_MOBILE = 'mobile'
USER_DEMO = 'demo_user'
USER_UNKNOWN = 'unknown'
USER_SUPPLY = 'supply'


class UserTypesField(forms.MultipleChoiceField):

    _USER_TYPES_CHOICES = [
        (USER_MOBILE, ugettext_lazy("All Mobile Workers")),
        (USER_DEMO, ugettext_lazy("Demo User")),
        (USER_UNKNOWN, ugettext_lazy("Unknown Users")),
        (USER_SUPPLY, ugettext_lazy("CommCare Supply")),
    ]
    widget = Select2MultipleChoiceWidget

    def __init__(self, *args, **kwargs):
        if len(args) == 0 and "choices" not in kwargs:  # choices is the first arg, and a kwarg
            kwargs['choices'] = self._USER_TYPES_CHOICES
        super(UserTypesField, self).__init__(*args, **kwargs)


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
        choices=[("", ugettext_lazy("Select model type")), ('case', ugettext_lazy('case')), ('form', ugettext_lazy('form'))]
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
                        placeholder=_("Select Module"),
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
                errors.append(forms.ValidationError(_("Module is required")))
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

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        super(BaseFilterExportDownloadForm, self).__init__(*args, **kwargs)

        self.fields['group'].choices = [("", "")] + map(
            lambda g: (g._id, g.name),
            Group.get_reporting_groups(self.domain_object.name)
        )

        if not self.domain_object.uses_locations:
            # don't use CommCare Supply as a user_types choice if the domain
            # is not a CommCare Supply domain.
            self.fields['user_types'].choices = self.fields['user_types'].choices[:-1]

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


class DashboardFeedFilterForm(BaseFilterExportDownloadForm):
    """
    A form used to configure the filters on a Dashboard Feed export
    """

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
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"placeholder": "YYYY-MM-DD"}),
        help_text='<small class="label label-default">{}</small>'.format(ugettext_lazy("YYYY-MM-DD")),
    )
    end_date = forms.DateField(
        label=ugettext_lazy("End Date"),
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"placeholder": "YYYY-MM-DD"}),
        help_text='<small class="label label-default">{}</small>'.format(ugettext_lazy("YYYY-MM-DD")),
    )

    @property
    def extra_fields(self):
        return [
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
                crispy.Field("start_date", ng_model="formData.start_date",),
                ng_show="formData.date_range === 'range' || formData.date_range === 'since'"
            ),
            crispy.Div(
                crispy.Field("end_date", ng_model="formData.end_date"),
                ng_show="formData.date_range === 'range'"
            )
        ]

    def to_export_instance_filters(self):
        """
        Serialize the bound form as an ExportInstanceFilters object.
        """
        return ExportInstanceFilters(
            date_period=DatePeriod(
                period_type=self.cleaned_data['date_range'],
                days=self.cleaned_data['days'],
                begin=self.cleaned_data['start_date'],
                end=self.cleaned_data['end_date'],
            ),
            type_or_group=self.cleaned_data['type_or_group'],
            user_types=self.cleaned_data['user_types'],
            group=self.cleaned_data['group']
        )

    @classmethod
    def get_form_data_from_export_instance_filters(cls, export_instance_filters):
        """
        Return a dictionary representing the form data from a given ExportInstanceFilters.
        This is used to populate a form from an existing export instance
        :param export_instance_filters:
        :return:
        """
        if export_instance_filters:
            date_period = export_instance_filters.date_period
            return {
                "date_range": date_period.period_type if date_period else None,
                "days": date_period.days if date_period else None,
                "start_date": date_period.begin if date_period else None,
                "end_date": date_period.end if date_period else None,
                "type_or_group": export_instance_filters['type_or_group'],
                "user_types": export_instance_filters['user_types'],
                "group": export_instance_filters['group'],
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
            "The timezone for this export is %(timezone)s."
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

    def get_multimedia_task_kwargs(self, export, download_id):
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
            'user_types': self._get_es_user_types(),
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
        from corehq.apps.export.filter_builders import CouchFormExportFilterBuilder
        return CouchFormExportFilterBuilder(
            self.domain_object.name,
            self.timezone,
            self.cleaned_data['type_or_group'],
            self.cleaned_data['group'],
            self.cleaned_data['user_types'],
            self.cleaned_data['date_range'],
        ).get_filter()

    def get_multimedia_task_kwargs(self, export, download_id):
        kwargs = super(FilterFormCouchExportDownloadForm, self).get_multimedia_task_kwargs(export, download_id)
        kwargs['export_is_legacy'] = True
        return kwargs


class FilterFormESExportDownloadForm(GenericFilterFormExportDownloadForm):

    def get_edit_url(self, export):
        from corehq.apps.export.views import EditNewCustomFormExportView
        return reverse(EditNewCustomFormExportView.urlname,
                       args=(self.domain_object.name, export._id))

    def get_form_filter(self):
        from corehq.apps.export.filter_builders import ESFormExportFilterBuilder
        return ESFormExportFilterBuilder(
            self.domain_object.name,
            self.timezone,
            self.cleaned_data['type_or_group'],
            self.cleaned_data['group'],
            self.cleaned_data['user_types'],
            self.cleaned_data['date_range'],
        ).get_filter()

    def get_multimedia_task_kwargs(self, export, download_id):
        kwargs = super(FilterFormESExportDownloadForm, self).get_multimedia_task_kwargs(export, download_id)
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
        from corehq.apps.export.filter_builders import CouchCaseExportFilterBuilder
        return CouchCaseExportFilterBuilder(
            self.domain_object.name,
            self.timezone,
            self.cleaned_data['type_or_group'],
            self.cleaned_data['group'],
            self.cleaned_data['user_types'],
            None,
        ).get_filter()


class FilterCaseESExportDownloadForm(GenericFilterCaseExportDownloadForm):
    _export_type = 'case'

    date_range = DateSpanField(
        label=ugettext_lazy("Date Range"),
        required=True,
        help_text="Export cases modified in this date range",
    )

    def __init__(self, domain_object, timezone, *args, **kwargs):
        self.timezone = timezone
        super(FilterCaseESExportDownloadForm, self).__init__(domain_object, timezone, *args, **kwargs)

        # update date_range filter's initial values to span the entirety of
        # the domain's submission range
        default_datespan = datespan_from_beginning(self.domain_object, self.timezone)
        self.fields['date_range'].widget = DateRangePickerWidget(
            default_datespan=default_datespan
        )


    def get_edit_url(self, export):
        from corehq.apps.export.views import EditNewCustomCaseExportView
        return reverse(EditNewCustomCaseExportView.urlname,
                       args=(self.domain_object.name, export.get_id))

    def get_case_filter(self):
        from corehq.apps.export.filter_builders import ESCaseExportFilterBuilder
        return ESCaseExportFilterBuilder(
            self.domain_object.name,
            self.timezone,
            self.cleaned_data['type_or_group'],
            self.cleaned_data['group'],
            self.cleaned_data['user_types'],
            self.cleaned_data['date_range'],
        ).get_filter()

    @property
    def extra_fields(self):
        return [
            crispy.Field(
                'date_range',
                ng_model='formData.date_range',
                ng_required='true',
            ),
        ]
