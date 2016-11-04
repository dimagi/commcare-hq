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
    ModifiedOnRangeFilter, FormSubmittedByFilter, NOT
)
from corehq.apps.es.users import user_ids_at_locations_and_descendants
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.users import LocationRestrictedMobileWorkerFilter
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
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

from corehq.util import flatten_list


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

        if not self.domain_object.uses_locations:
            # don't use CommCare Supply as a user_types choice if the domain
            # is not a CommCare Supply domain.
            self.fields['user_types'].choices = self._USER_TYPES_CHOICES[:-1]

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

    def _get_es_user_types(self):
        """
        Return a list of elastic search user types (each item in the return list
        is in corehq.pillows.utils.USER_TYPES) corresponding to the selected
        export user types.
        """
        es_user_types = []
        export_user_types = self.cleaned_data['user_types']
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
        }


class GenericFilterFormExportDownloadForm(BaseFilterExportDownloadForm):
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

    def _get_datespan(self):
        date_range = self.cleaned_data['date_range']
        dates = date_range.split(DateRangePickerWidget.separator)
        startdate = dateutil.parser.parse(dates[0])
        enddate = dateutil.parser.parse(dates[1])
        return DateSpan(startdate, enddate)

    def get_form_filter(self):
        raise NotImplementedError

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
        datespan = self._get_datespan()
        if datespan.is_valid():
            datespan.set_timezone(self.timezone)
            return SerializableFunction(datespan_export_filter,
                                        datespan=datespan)

    def get_multimedia_task_kwargs(self, export, download_id):
        kwargs = super(FilterFormCouchExportDownloadForm, self).get_multimedia_task_kwargs(export, download_id)
        kwargs['export_is_legacy'] = True
        return kwargs


class EmwfFilterExportMixin(object):
    # filter to be used to identify objects(forms/cases) for users
    export_user_filter = FormSubmittedByFilter

    # filter class for including dynamic fields in the context of the view as dynamic_filters
    dynamic_filter_class = LocationRestrictedMobileWorkerFilter

    def _get_user_ids(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['l__e80c5e54ab552245457d2546d0cdbb05']
        :return: ['e80c5e54ab552245457d2546d0cdbb05']
        """
        return self.dynamic_filter_class.selected_user_ids(mobile_user_and_group_slugs)

    def _get_users_filter(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['u__e80c5e54ab552245457d2546d0cdbb05']
        :return: User filter set by inheriting class
        """
        user_ids = self._get_user_ids(mobile_user_and_group_slugs)
        if user_ids:
            return self.export_user_filter(user_ids)

    def _get_locations_ids(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['l__e80c5e54ab552245457d2546d0cdbb05']
        :return: ['e80c5e54ab552245457d2546d0cdbb05']
        """
        return self.dynamic_filter_class.selected_location_ids(mobile_user_and_group_slugs)

    def _get_locations_filter(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['l__e80c5e54ab552245457d2546d0cdbb05']
        :return: User filter with users at filtered locations and their descendants
        """
        location_ids = self._get_locations_ids(mobile_user_and_group_slugs)
        if location_ids:
            user_ids = user_ids_at_locations_and_descendants(location_ids)
            return self.export_user_filter(user_ids)

    def _get_group_ids(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['g__e80c5e54ab552245457d2546d0cdbb05']
        :return: ['e80c5e54ab552245457d2546d0cdbb05']
        """
        return self.dynamic_filter_class.selected_group_ids(mobile_user_and_group_slugs)

    def _get_es_user_types(self, mobile_user_and_group_slugs):
        """
        :param: ['t__0', 't__1']
        :return: int values corresponding to user types as in HQUserType
        HQUserType user_type_mapping to be used for mapping
        """
        return self.dynamic_filter_class.selected_user_types(mobile_user_and_group_slugs)

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
                 .fields([]))
        user_ids = query.run().doc_ids

        if commtrack:
            user_ids.append("commtrack-system")
        if demo:
            user_ids.append("demo_user_group_id")
            user_ids.append("demo_user")
        return user_ids


class EmwfFilterFormExport(EmwfFilterExportMixin, GenericFilterFormExportDownloadForm):
    """
    Generic Filter form including dynamic filters using LocationRestrictedMobileWorkerFilter
    overrides few methods from GenericFilterFormExportDownloadForm for dynamic fields over form fields
    """
    export_user_filter = FormSubmittedByFilter
    dynamic_filter_class = LocationRestrictedMobileWorkerFilter

    def __init__(self, domain_object, *args, **kwargs):
        self.domain_object = domain_object
        self.skip_layout = True
        super(EmwfFilterFormExport, self).__init__(domain_object, *args, **kwargs)

        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-3'
        self.helper.layout = Layout(
            *super(EmwfFilterFormExport, self).extra_fields
        )

    def get_form_filter(self, mobile_user_and_group_slugs, can_access_all_locations):
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
        form_filters = []
        if can_access_all_locations:
            form_filters += filter(None, [
                self._get_group_filter(mobile_user_and_group_slugs),
                self._get_user_type_filter(mobile_user_and_group_slugs),
            ])

        form_filters += filter(None, [
            self._get_users_filter(mobile_user_and_group_slugs),
            self._get_locations_filter(mobile_user_and_group_slugs)
        ])

        form_filters = flatten_list(form_filters)
        form_filters = [OR(*form_filters)]
        form_filters.append(self._get_datespan_filter())
        return form_filters

    def _get_group_filter(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['g__e80c5e54ab552245457d2546d0cdbb03']
        :return: GroupFormSubmittedByFilter filter which filters for users for selected groups
        """
        group_ids = self._get_group_ids(mobile_user_and_group_slugs)
        if group_ids:
            return GroupFormSubmittedByFilter(group_ids)

    def _get_user_type_filter(self, mobile_user_and_group_slugs):
        """
        :param mobile_user_and_group_slugs: ['t__0', 't__1']
        :return: FormSubmittedByFilter with user_ids for selected user types
        """
        user_types = self._get_es_user_types(mobile_user_and_group_slugs)
        if user_types:
            form_filters = []
            if HQUserType.REGISTERED in user_types:
                form_filters.append(UserTypeFilter(self._USER_MOBILE))
            user_ids = self.get_user_ids_for_user_types(
                admin=HQUserType.ADMIN in user_types,
                unknown=HQUserType.UNKNOWN in user_types,
                demo=HQUserType.DEMO_USER in user_types,
                commtrack=False,
            )
            form_filters.append(FormSubmittedByFilter(user_ids))
            return form_filters

    def get_edit_url(self, export):
        from corehq.apps.export.views import EditNewCustomFormExportView
        return reverse(EditNewCustomFormExportView.urlname,
                       args=(self.domain_object.name, export._id))

    def _get_datespan_filter(self):
        datespan = self._get_datespan()
        if datespan.is_valid():
            datespan.set_timezone(self.timezone)
            return ReceivedOnRangeFilter(gte=datespan.startdate, lt=datespan.enddate + timedelta(days=1))

    def get_multimedia_task_kwargs(self, export, download_id):
        kwargs = super(EmwfFilterFormExport, self).get_multimedia_task_kwargs(export, download_id)
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

    date_range = forms.CharField(
        label=ugettext_lazy("Date Range"),
        required=True,
        widget=DateRangePickerWidget(),
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

    def _get_datespan(self):
        date_range = self.cleaned_data['date_range']
        dates = date_range.split(DateRangePickerWidget.separator)
        startdate = dateutil.parser.parse(dates[0])
        enddate = dateutil.parser.parse(dates[1])
        return DateSpan(startdate, enddate)

    def _get_datespan_filter(self):
        datespan = self._get_datespan()
        if datespan.is_valid():
            datespan.set_timezone(self.timezone)
            return ModifiedOnRangeFilter(gte=datespan.startdate, lt=datespan.enddate + timedelta(days=1))

    def get_case_filter(self, mobile_user_and_group_slugs, can_access_all_locations):
        """
        Taking reference from CaseListMixin allow filters depending on locations access
        :param mobile_user_and_group_slugs: ['g__e80c5e54ab552245457d2546d0cdbb03', 't__0', 't__1']
        :param can_access_all_locations: if request user has full organization access permission
        :return: set of filters
        """
        if can_access_all_locations and self.dynamic_filter_class.show_all_data(mobile_user_and_group_slugs):
            # if all data then just filter by date
            case_filter = []
        elif can_access_all_locations and self.dynamic_filter_class.show_project_data(mobile_user_and_group_slugs):
            # show projects data except user_ids for user types excluded
            user_types = LocationRestrictedMobileWorkerFilter.selected_user_types(mobile_user_and_group_slugs)
            ids_to_exclude = self.get_user_ids_for_user_types(
                admin=HQUserType.ADMIN not in user_types,
                unknown=HQUserType.UNKNOWN not in user_types,
                demo=HQUserType.DEMO_USER not in user_types,
                commtrack=False,
            )
            case_filter = [NOT(OwnerFilter(ids_to_exclude))]
        else:
            case_filter = self._get_filters_from_slugs(mobile_user_and_group_slugs, can_access_all_locations)

        date_filter = self._get_datespan_filter()
        if date_filter:
            case_filter.append(date_filter)

        return case_filter

    def _get_filters_from_slugs(self, mobile_user_and_group_slugs, can_access_all_locations):
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
            group_ids = self._get_group_ids(mobile_user_and_group_slugs)

        if group_ids:
            groups_static_user_ids = Group.get_static_user_ids_for_groups(group_ids)
            groups_static_user_ids = flatten_list(groups_static_user_ids)
            owner_filter_ids = group_ids + groups_static_user_ids
            last_modified_filter_ids = groups_static_user_ids
        else:
            if can_access_all_locations:
                # case sharing groups returns case sharing groups and locations wrapped as Group
                case_sharing_ids = [g.get_id for g in
                                    Group.get_case_sharing_groups(self.domain_object.name)]
            else:
                case_sharing_ids = SQLLocation.get_case_sharing_locations_ids(self.domain_object.name)
            owner_filter_ids = case_sharing_ids
            last_modified_filter_ids = case_sharing_ids

        return [OR(
            OwnerFilter(owner_filter_ids),
            LastModifiedByFilter(last_modified_filter_ids),
            *self._get_group_independent_filters(mobile_user_and_group_slugs, can_access_all_locations)
        )]

    def _get_group_independent_filters(self, mobile_user_and_group_slugs, can_access_all_locations):
        # filters for location and users for both and user type in case of full access
        if can_access_all_locations:
            user_types = self.dynamic_filter_class.selected_user_types(mobile_user_and_group_slugs)
            ids_to_include = self.get_user_ids_for_user_types(
                admin=HQUserType.ADMIN in user_types,
                unknown=HQUserType.UNKNOWN in user_types,
                demo=HQUserType.DEMO_USER in user_types,
                commtrack=False,
            )
            default_filters = [OwnerFilter(ids_to_include)]
        else:
            default_filters = []
        # filters for cases owned by users at locations and locations itself
        default_filters.append(self._get_locations_filter(mobile_user_and_group_slugs))
        default_filters.append(self.export_user_filter(self._get_locations_ids(mobile_user_and_group_slugs)))

        default_filters.append(self._get_users_filter(mobile_user_and_group_slugs))
        return filter(None, default_filters)

    @property
    def extra_fields(self):
        return [
            crispy.Field(
                'date_range',
                ng_model='formData.date_range',
                ng_required='true',
            ),
        ]
