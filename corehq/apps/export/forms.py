from datetime import timedelta
import dateutil
from django import forms
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _, ugettext_lazy
from unidecode import unidecode

from corehq.apps.export.filters import (
    ReceivedOnRangeFilter,
    GroupFormSubmittedByFilter,
    OR, OwnerFilter, LastModifiedByFilter, UserTypeFilter,
    OwnerTypeFilter, ModifiedOnRangeFilter
)
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
from corehq.pillows import utils
from couchexport.util import SerializableFunction

from crispy_forms.bootstrap import InlineField
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from crispy_forms.layout import Layout
from dimagi.utils.dates import DateSpan

_USER_MOBILE = 'mobile'
_USER_DEMO = 'demo_user'
_USER_UNKNOWN = 'unknown'
_USER_SUPPLY = 'supply'


def _get_filtered_users(domain, user_types):
    user_types = _user_type_choices_to_es_user_types(user_types)
    user_filter_toggles = [
        _USER_MOBILE in user_types,
        _USER_DEMO in user_types,
        # The following line results in all users who match the
        # HQUserType.ADMIN filter to be included if the unknown users
        # filter is selected.
        _USER_UNKNOWN in user_types,
        _USER_UNKNOWN in user_types,
        _USER_SUPPLY in user_types
    ]
    # todo refactor HQUserType
    user_filters = HQUserType._get_manual_filterset(
        (True,) * HQUserType.count,
        user_filter_toggles
    )
    return users_matching_filter(domain, user_filters)


def _user_type_choices_to_es_user_types(choices):
    """
    Return a list of elastic search user types (each item in the return list
    is in corehq.pillows.utils.USER_TYPES) corresponding to the selected
    export user types.
    """
    es_user_types = []
    export_to_es_user_types_map = {
        _USER_MOBILE: [utils.MOBILE_USER_TYPE],
        _USER_DEMO: [utils.DEMO_USER_TYPE],
        _USER_UNKNOWN: [
            utils.UNKNOWN_USER_TYPE, utils.SYSTEM_USER_TYPE, utils.WEB_USER_TYPE
        ],
        _USER_SUPPLY: [utils.COMMCARE_SUPPLY_USER_TYPE]
    }
    for type_ in choices:
        es_user_types.extend(export_to_es_user_types_map[type_])
    return es_user_types


class UserTypesField(forms.MultipleChoiceField):

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

    def __init__(self, *args, **kwargs):
        super(CreateExportTagForm, self).__init__(*args, **kwargs)

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


class BaseExportFilterBuilder(object):
    """
    A class for building export filters.
    Instantiate with selected filter options, and get the corresponding export filters with get_filters()
    """
    def __init__(self, domain, timezone, type_or_group, group, user_types, date_interval):
        """
        :param domain:
        :param timezone:
        :param type_or_group:
        :param group:
        :param user_types:
        :param date_interval: A DateSpan or DatePeriod
        """
        self.domain = domain
        self.timezone = timezone
        self.type_or_group = type_or_group
        self.group = group
        self.user_types = user_types
        self.date_interval = date_interval

    def get_filter(self):
        raise NotImplementedError


class ESFormExportFilterBuilder(BaseExportFilterBuilder):

    def get_filter(self):
        return filter(None, [
            self._get_datespan_filter(),
            self._get_group_filter(),
            self._get_user_filter()
        ])

    def _get_datespan_filter(self):
        if self.date_interval and (not hasattr(self.date_interval, "is_valid") or self.date_interval.is_valid()):
            try:
                self.date_interval.set_timezone(self.timezone)
            except AttributeError:
                # Some date_intervals (e.g. DatePeriod instances) don't have a set_timezone method.
                pass
            return ReceivedOnRangeFilter(gte=self.date_interval.startdate, lt=self.date_interval.enddate + timedelta(days=1))

    def _get_group_filter(self):
        if self.group and self.type_or_group == "group":
            return GroupFormSubmittedByFilter(self.group)

    def _get_user_filter(self):
        if self.user_types and self.type_or_group == "users":
            return UserTypeFilter(_user_type_choices_to_es_user_types(self.user_types))


class CouchFormExportFilterBuilder(BaseExportFilterBuilder):

    def get_filter(self):
        form_filter = SerializableFunction(app_export_filter, app_id=None)
        datespan_filter = self._get_datespan_filter()
        if datespan_filter:
            form_filter &= datespan_filter
        form_filter &= self._get_user_or_group_filter()
        return form_filter

    def _get_user_or_group_filter(self):
        if self.group:
            # filter by groups
            group = Group.get(self.group)
            return SerializableFunction(group_filter, group=group)
        # filter by users
        return SerializableFunction(users_filter, users=_get_filtered_users(self.domain, self.user_types))

    def _get_datespan_filter(self):
        try:
            if not self.date_interval.is_valid():
                return
            self.date_interval.set_timezone(self.timezone)
        except AttributeError:
            pass  # TODO: Explain this
        return SerializableFunction(datespan_export_filter, datespan=self.date_interval)


class ESCaseExportFilterBuilder(BaseExportFilterBuilder):

    def get_filter(self):
        if self.group:
            group = Group.get(self.group)
            user_ids = set(group.get_static_user_ids())
            case_filter = [OR(
                OwnerFilter(group._id),
                OwnerFilter(user_ids),
                LastModifiedByFilter(user_ids)
            )]
        else:
            case_sharing_groups = [g.get_id for g in Group.get_case_sharing_groups(self.domain)]
            case_filter = [OR(
                OwnerTypeFilter(_user_type_choices_to_es_user_types(self.user_types)),
                OwnerFilter(case_sharing_groups),
                LastModifiedByFilter(case_sharing_groups)
            )]

        date_filter = self._get_datespan_filter()
        if date_filter:
            case_filter.append(date_filter)

        return case_filter


    def _get_datespan_filter(self):
        try:
            if not self.date_interval.is_valid():
                return
            self.date_interval.set_timezone(self.timezone)
        except AttributeError:
            pass  # TODO: Explain this
        return ModifiedOnRangeFilter(
            gte=self.date_interval.startdate, lt=self.date_interval.enddate + timedelta(days=1)
        )


class CouchCaseExportFilterBuilder(BaseExportFilterBuilder):

    def get_filter(self):
        if self.group:
            group = Group.get(self.group)
            return SerializableFunction(case_group_filter, group=group)
        case_sharing_groups = [g.get_id for g in Group.get_case_sharing_groups(self.domain)]
        return SerializableFunction(
            case_users_filter,
            users=_get_filtered_users(self.domain, self.user_types),
            groups=case_sharing_groups
        )



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
    group = forms.CharField(
        label=ugettext_lazy("Select Group"),
        required=False,
    )

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        super(BaseFilterExportDownloadForm, self).__init__(*args, **kwargs)

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
