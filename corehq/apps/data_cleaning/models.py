import re
import uuid

from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy, gettext as _

from corehq.apps.case_search.const import METADATA_IN_REPORTS
from corehq.apps.data_cleaning.exceptions import (
    UnsupportedActionException,
    UnsupportedFilterValueException,
)
from corehq.apps.es import CaseSearchES


class BulkEditSessionType:
    CASE = 'case'
    FORM = 'form'
    CHOICES = (
        (CASE, "Case"),
        (FORM, "Form"),
    )


class BulkEditSession(models.Model):
    user = models.ForeignKey(User, related_name="bulk_edit_sessions", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255, db_index=True)
    created_on = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    session_type = models.CharField(
        max_length=4,
        choices=BulkEditSessionType.CHOICES,
    )
    identifier = models.CharField(max_length=255, db_index=True)
    committed_on = models.DateTimeField(null=True, blank=True)
    task_id = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    result = models.JSONField(null=True, blank=True)
    completed_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_on"]

    @classmethod
    def get_active_case_session(cls, user, domain_name, case_type):
        return cls._get_active_session(user, domain_name, case_type, BulkEditSessionType.CASE)

    @classmethod
    def get_active_form_session(cls, user, domain_name, xmlns):
        return cls._get_active_session(user, domain_name, xmlns, BulkEditSessionType.FORM)

    @classmethod
    def _get_active_session(cls, user, domain_name, identifier, session_type):
        try:
            return cls.objects.get(
                user=user,
                domain=domain_name,
                identifier=identifier,
                session_type=session_type,
                committed_on=None,
                completed_on=None,
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def new_case_session(cls, user, domain_name, case_type):
        case_session = cls.objects.create(
            user=user,
            domain=domain_name,
            identifier=case_type,
            session_type=BulkEditSessionType.CASE,
        )
        BulkEditPinnedFilter.create_default_filters(case_session)
        BulkEditColumn.create_default_columns(case_session)
        return case_session

    @classmethod
    def restart_case_session(cls, user, domain_name, case_type):
        previous_session = cls.get_active_case_session(user, domain_name, case_type)
        previous_session.delete()
        new_session = cls.new_case_session(user, domain_name, case_type)
        return new_session

    @classmethod
    def new_form_session(cls, user, domain_name, xmlns):
        raise NotImplementedError("Form data cleaning sessions are not yet supported!")

    @classmethod
    def get_committed_sessions(cls, user, domain_name):
        return cls.objects.filter(user=user, domain=domain_name, committed_on__isnull=False)

    @property
    def form_ids(self):
        if self.result is None or 'form_ids' not in self.result:
            return []
        return self.result['form_ids']

    @property
    def percent_complete(self):
        if self.result is None or 'percent' not in self.result:
            return None
        return round(self.result['percent'])

    @property
    def has_any_filtering(self):
        return self.has_pinned_values or self.has_filters

    def reset_filtering(self):
        self.reset_filters()
        self.reset_pinned_filters()

    @property
    def has_filters(self):
        return self.filters.count() > 0

    def reset_filters(self):
        self.filters.all().delete()

    @property
    def has_pinned_values(self):
        return any(self.pinned_filters.values_list('value', flat=True))

    def reset_pinned_filters(self):
        for pinned_filter in self.pinned_filters.all():
            pinned_filter.value = None
            pinned_filter.save()

    def add_filter(self, prop_id, data_type, match_type, value=None):
        BulkEditFilter.objects.create(
            session=self,
            index=self.filters.count(),
            prop_id=prop_id,
            data_type=data_type,
            match_type=match_type,
            value=value,
        )

    def remove_filter(self, filter_id):
        self.filters.get(filter_id=filter_id).delete()
        remaining_ids = self.filters.values_list('filter_id', flat=True)
        self.update_filter_order(remaining_ids)

    def update_filter_order(self, filter_ids):
        """
        This updates the order of filters for this session
        :param filter_ids: list of uuids matching filter_id field of BulkEditFilters
        """
        if len(filter_ids) != self.filters.count():
            raise ValueError("the lengths of filter_ids and available filters do not match")
        for index, filter_id in enumerate(filter_ids):
            active_filter = self.filters.get(filter_id=filter_id)
            active_filter.index = index
            active_filter.save()

    def get_queryset(self):
        query = CaseSearchES().domain(self.domain).case_type(self.identifier)
        query = self._apply_filters(query)
        query = self._apply_pinned_filters(query)
        return query

    def _apply_filters(self, query):
        xpath_expressions = []
        for custom_filter in self.filters.all():
            query = custom_filter.filter_query(query)
            column_xpath = custom_filter.get_xpath_expression()
            if column_xpath is not None:
                xpath_expressions.append(column_xpath)
        if xpath_expressions:
            query = query.xpath_query(self.domain, " and ".join(xpath_expressions))
        return query

    def _apply_pinned_filters(self, query):
        for pinned_filter in self.pinned_filters.all():
            query = pinned_filter.filter_query(query)
        return query

    def update_result(self, record_count, form_id=None):
        result = self.result or {}

        if 'form_ids' not in result:
            result['form_ids'] = []
        if 'record_count' not in result:
            result['record_count'] = 0
        if 'percent' not in result:
            result['percent'] = 0

        if form_id:
            result['form_ids'].append(form_id)
        result['record_count'] += record_count
        if self.records.count() == 0:
            result['percent'] = 100
        else:
            result['percent'] = result['record_count'] * 100 / self.records.count()

        self.result = result
        self.save()


class DataType:
    TEXT = 'text'
    INTEGER = 'integer'
    PHONE_NUMBER = 'phone_number'
    DECIMAL = 'decimal'
    DATE = 'date'
    TIME = 'time'
    DATETIME = 'datetime'
    SINGLE_OPTION = 'single_option'
    MULTIPLE_OPTION = 'multiple_option'
    GPS = 'gps'
    BARCODE = 'barcode'
    PASSWORD = 'password'

    CHOICES = (
        (TEXT, TEXT),
        (INTEGER, INTEGER),
        (PHONE_NUMBER, PHONE_NUMBER),
        (DECIMAL, DECIMAL),
        (DATE, DATE),
        (TIME, TIME),
        (DATETIME, DATETIME),
        (SINGLE_OPTION, SINGLE_OPTION),
        (MULTIPLE_OPTION, MULTIPLE_OPTION),
        (GPS, GPS),
        (BARCODE, BARCODE),
        (PASSWORD, PASSWORD),
    )

    FORM_CHOICES = (
        (TEXT, gettext_lazy("Text")),
        (INTEGER, gettext_lazy("Integer")),
        (DECIMAL, gettext_lazy("Decimal")),
        (PHONE_NUMBER, gettext_lazy("Phone Number or Numeric ID")),
        (DATE, gettext_lazy("Date")),
        (TIME, gettext_lazy("Time")),
        (DATETIME, gettext_lazy("Date and Time")),
        (SINGLE_OPTION, gettext_lazy("Single Option")),
        (MULTIPLE_OPTION, gettext_lazy("Multiple Option")),
        (GPS, gettext_lazy("GPS")),
        (BARCODE, gettext_lazy("Barcode")),
        (PASSWORD, gettext_lazy("Password")),
    )

    CASE_CHOICES = (
        (TEXT, gettext_lazy("Text")),
        (INTEGER, gettext_lazy("Number")),
        (DATE, gettext_lazy("Date")),
        (DATETIME, gettext_lazy("Date and Time")),
        (MULTIPLE_OPTION, gettext_lazy("Multiple Choice")),
        (BARCODE, gettext_lazy("Barcode")),
        (GPS, gettext_lazy("GPS")),
        (PHONE_NUMBER, gettext_lazy("Phone Number or Numeric ID")),
        (PASSWORD, gettext_lazy("Password")),
    )

    FILTER_CATEGORY_TEXT = 'filter_text'
    FILTER_CATEGORY_NUMBER = 'filter_number'
    FILTER_CATEGORY_DATE = 'filter_date'
    FILTER_CATEGORY_MULTI_SELECT = 'filter_multi_select'

    FILTER_CATEGORY_DATA_TYPES = {
        FILTER_CATEGORY_TEXT: (TEXT, PHONE_NUMBER, BARCODE, PASSWORD, GPS, SINGLE_OPTION, TIME,),
        FILTER_CATEGORY_NUMBER: (INTEGER, DECIMAL,),
        FILTER_CATEGORY_DATE: (DATE, DATETIME,),
        FILTER_CATEGORY_MULTI_SELECT: (MULTIPLE_OPTION,),
    }

    ICON_CLASSES = {
        TEXT: 'fcc fcc-fd-text',
        INTEGER: 'fcc fcc-fd-numeric',
        PHONE_NUMBER: 'fa fa-signal',
        DECIMAL: 'fcc fcc-fd-decimal',
        DATE: 'fa-solid fa-calendar-days',
        TIME: 'fa-regular fa-clock',
        DATETIME: 'fcc fcc-fd-datetime',
        SINGLE_OPTION: 'fcc fcc-fd-single-select',
        MULTIPLE_OPTION: 'fcc fcc-fd-multi-select',
        GPS: 'fa-solid fa-location-dot',
        BARCODE: 'fa fa-barcode',
        PASSWORD: 'fa fa-key',
    }

    @classmethod
    def get_filter_category(cls, data_type):
        for category, valid_data_types in cls.FILTER_CATEGORY_DATA_TYPES.items():
            if data_type in valid_data_types:
                return category


class FilterMatchType:
    EXACT = "exact"
    IS_NOT = "is_not"

    STARTS = "starts"
    STARTS_NOT = "starts_not"

    IS_EMPTY = "is_empty"  # empty string
    IS_NOT_EMPTY = "is_not_empty"

    IS_MISSING = "missing"  # un-set
    IS_NOT_MISSING = "not_missing"

    FUZZY = "fuzzy"  # will use fuzzy-match from CQL
    FUZZY_NOT = "not_fuzzy"  # will use not(fuzzy-match()) from CQL

    PHONETIC = "phonetic"  # will use phonetic-match from CQL
    PHONETIC_NOT = "not_phonetic"  # will use not(phonetic-match()) from CQL

    LESS_THAN = "lt"
    GREATER_THAN = "gt"

    LESS_THAN_EQUAL = "lte"
    GREATER_THAN_EQUAL = "gte"

    IS_ANY = "is_any"  # we will use selected-any from CQL
    IS_NOT_ANY = "is_not_any"  # we will use not(selected-any()) from CQL

    IS_ALL = "is_all"  # we will use selected-all from CQL
    IS_NOT_ALL = "is_not_all"  # we will use not(selected-all()) from CQL

    ALL_CHOICES = (
        (EXACT, EXACT),
        (IS_NOT, IS_NOT),
        (STARTS, STARTS),
        (STARTS_NOT, STARTS_NOT),
        (IS_EMPTY, IS_EMPTY),
        (IS_NOT_EMPTY, IS_NOT_EMPTY),
        (IS_MISSING, IS_MISSING),
        (IS_NOT_MISSING, IS_NOT_MISSING),
        (FUZZY, FUZZY),
        (FUZZY_NOT, FUZZY_NOT),
        (PHONETIC, PHONETIC),
        (PHONETIC_NOT, PHONETIC_NOT),
        (LESS_THAN, LESS_THAN),
        (GREATER_THAN, GREATER_THAN),
        (LESS_THAN_EQUAL, LESS_THAN_EQUAL),
        (GREATER_THAN_EQUAL, GREATER_THAN_EQUAL),
        (IS_ANY, IS_ANY),
        (IS_NOT_ANY, IS_NOT_ANY),
        (IS_ALL, IS_ALL),
        (IS_NOT_ALL, IS_NOT_ALL),
    )

    # choices valid for all data types
    ALL_DATA_TYPES_CHOICES = (
        (IS_EMPTY, gettext_lazy("is empty")),
        (IS_NOT_EMPTY, gettext_lazy("is not empty")),
        (IS_MISSING, gettext_lazy("is missing")),
        (IS_NOT_MISSING, gettext_lazy("is not missing")),
    )

    TEXT_CHOICES = (
        (EXACT, gettext_lazy("is exactly")),
        (IS_NOT, gettext_lazy("is not")),
        (STARTS, gettext_lazy("starts with")),
        (STARTS_NOT, gettext_lazy("does not start with")),
        (FUZZY, gettext_lazy("is like")),
        (FUZZY_NOT, gettext_lazy("is not like")),
        (PHONETIC, gettext_lazy("sounds like")),
        (PHONETIC_NOT, gettext_lazy("does not sound like")),
    )

    MULTI_SELECT_CHOICES = (
        (IS_ANY, gettext_lazy("is any")),
        (IS_NOT_ANY, gettext_lazy("is not any")),
        (IS_ALL, gettext_lazy("is all")),
        (IS_NOT_ALL, gettext_lazy("is not all")),
    )

    NUMBER_CHOICES = (
        (EXACT, gettext_lazy("equals")),
        (IS_NOT, gettext_lazy("does not equal")),
        (LESS_THAN, gettext_lazy("less than")),
        (LESS_THAN_EQUAL, gettext_lazy("less than or equal to")),
        (GREATER_THAN, gettext_lazy("greater than")),
        (GREATER_THAN_EQUAL, gettext_lazy("greater than or equal to")),
    )

    DATE_CHOICES = (
        (EXACT, gettext_lazy("on")),
        (LESS_THAN, gettext_lazy("before")),
        (LESS_THAN_EQUAL, gettext_lazy("before or on")),
        (GREATER_THAN, gettext_lazy("after")),
        (GREATER_THAN_EQUAL, gettext_lazy("on or after")),
    )


class BulkEditFilter(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="filters", on_delete=models.CASCADE)
    filter_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    index = models.IntegerField(default=0)
    prop_id = models.CharField(max_length=255)  # case property or form question_id
    data_type = models.CharField(
        max_length=15,
        default=DataType.TEXT,
        choices=DataType.CHOICES,
    )
    match_type = models.CharField(
        max_length=12,
        default=FilterMatchType.EXACT,
        choices=FilterMatchType.ALL_CHOICES,
    )
    value = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["index"]

    @property
    def is_editable_property(self):
        from corehq.apps.data_cleaning.utils.cases import get_case_property_details
        property_details = get_case_property_details(self.session.domain, self.session.identifier)
        return property_details.get(self.prop_id, {}).get('is_editable', True)

    @property
    def human_readable_data_type(self):
        return dict(DataType.CASE_CHOICES).get(self.data_type, _("unknown"))

    @property
    def human_readable_match_type(self):
        category = DataType.get_filter_category(self.data_type)
        match_to_text = {
            DataType.FILTER_CATEGORY_TEXT: dict(
                FilterMatchType.TEXT_CHOICES + FilterMatchType.ALL_DATA_TYPES_CHOICES
            ),
            DataType.FILTER_CATEGORY_NUMBER: dict(
                FilterMatchType.NUMBER_CHOICES + FilterMatchType.ALL_DATA_TYPES_CHOICES
            ),
            DataType.FILTER_CATEGORY_DATE: dict(
                FilterMatchType.DATE_CHOICES + FilterMatchType.ALL_DATA_TYPES_CHOICES
            ),
            DataType.FILTER_CATEGORY_MULTI_SELECT: dict(
                FilterMatchType.MULTI_SELECT_CHOICES + FilterMatchType.ALL_DATA_TYPES_CHOICES
            ),
        }.get(category, {})
        return match_to_text.get(self.match_type, _("unknown"))

    def filter_query(self, query):
        filter_query_functions = {
            FilterMatchType.IS_EMPTY: lambda q: q.empty(self.prop_id),
            FilterMatchType.IS_NOT_EMPTY: lambda q: q.non_null(self.prop_id),
            FilterMatchType.IS_MISSING: lambda q: q.missing(self.prop_id),
            FilterMatchType.IS_NOT_MISSING: lambda q: q.exists(self.prop_id),
        }
        # if a property is not editable, then it can't be empty or missing
        # we need the `is_editable_property` check to avoid elasticsearch RequestErrors on system fields
        if self.match_type in filter_query_functions and self.is_editable_property:
            query = filter_query_functions[self.match_type](query)
        return query

    @staticmethod
    def is_data_and_match_type_valid(match_type, data_type):
        if match_type in dict(FilterMatchType.ALL_DATA_TYPES_CHOICES):
            # empty / missing is always valid regardless of data type
            return True

        matches_by_category = {
            DataType.FILTER_CATEGORY_TEXT: dict(FilterMatchType.TEXT_CHOICES),
            DataType.FILTER_CATEGORY_NUMBER: dict(FilterMatchType.NUMBER_CHOICES),
            DataType.FILTER_CATEGORY_DATE: dict(FilterMatchType.DATE_CHOICES),
            DataType.FILTER_CATEGORY_MULTI_SELECT: dict(FilterMatchType.MULTI_SELECT_CHOICES),
        }
        category = DataType.get_filter_category(data_type)
        if category:
            return match_type in matches_by_category[category]
        return False

    @staticmethod
    def get_quoted_value(value):
        has_single_quote = "'" in value
        has_double_quote = '"' in value
        if has_double_quote and has_single_quote:
            # It seems our current xpath parsing library has no way of escaping quotes.
            # A workaround could be to avoid xpath expression parsing altogether and have
            # all match_types use `filter_query` directly, but that would require more effort.
            # The option to use CaseSearchES `xpath_query` was chosen for development speed,
            # acknowledging that there are limitations. We can re-evaluate this decision
            # when filtering form data, as we don't have an `xpath_query` filter built for FormES.
            raise UnsupportedFilterValueException(
                """We cannot support both single quotes (') and double quotes (") in
                a filter value at this time."""
            )
        return f'"{value}"' if has_single_quote else f"'{value}'"

    def get_xpath_expression(self):
        """
        Assumption:
        - data_type and match_type combination was validated by the form that created this filter

        Limitations:
        - no support for multiple quote types (double and single) in the same value
        - no support for special whitespace characters (tab or newline)
        - no `xpath_query` support in `FormES`

        We can address limitations in later releases of this tool.
        """
        match_operators = {
            FilterMatchType.EXACT: '=',
            FilterMatchType.IS_NOT: '!=',
            FilterMatchType.LESS_THAN: '<',
            FilterMatchType.LESS_THAN_EQUAL: '<=',
            FilterMatchType.GREATER_THAN: '>',
            FilterMatchType.GREATER_THAN_EQUAL: '>=',
        }
        if self.match_type in match_operators:
            # we assume the data type was properly verified on creation
            is_number = self.data_type in DataType.FILTER_CATEGORY_DATA_TYPES[DataType.FILTER_CATEGORY_NUMBER]
            value = self.value if is_number else self.get_quoted_value(self.value)
            operator = match_operators[self.match_type]
            return f"{self.prop_id} {operator} {value}"

        match_expression = {
            FilterMatchType.STARTS: lambda x: f'starts-with({self.prop_id}, {x})',
            FilterMatchType.STARTS_NOT: lambda x: f'not(starts-with({self.prop_id}, {x}))',
            FilterMatchType.FUZZY: lambda x: f'fuzzy-match({self.prop_id}, {x})',
            FilterMatchType.FUZZY_NOT: lambda x: f'not(fuzzy-match({self.prop_id}, {x}))',
            FilterMatchType.PHONETIC: lambda x: f'phonetic-match({self.prop_id}, {x})',
            FilterMatchType.PHONETIC_NOT: lambda x: f'not(phonetic-match({self.prop_id}, {x}))',
            FilterMatchType.IS_ANY: lambda x: f'selected-any({self.prop_id}, {x})',
            FilterMatchType.IS_NOT_ANY: lambda x: f'not(selected-any({self.prop_id}, {x}))',
            FilterMatchType.IS_ALL: lambda x: f'selected-all({self.prop_id}, {x})',
            FilterMatchType.IS_NOT_ALL: lambda x: f'not(selected-all({self.prop_id}, {x}))',
        }
        if self.match_type in match_expression:
            quoted_value = self.get_quoted_value(self.value)
            return match_expression[self.match_type](quoted_value)


class PinnedFilterType:
    CASE_OWNERS = 'case_owners'
    CASE_STATUS = 'case_status'

    CHOICES = (
        (CASE_OWNERS, CASE_OWNERS),
        (CASE_STATUS, CASE_STATUS),
    )

    DEFAULT_FOR_CASE = (
        CASE_OWNERS, CASE_STATUS
    )


class BulkEditPinnedFilter(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="pinned_filters", on_delete=models.CASCADE)
    index = models.IntegerField(default=0)
    filter_type = models.CharField(
        max_length=11,
        choices=PinnedFilterType.CHOICES,
    )
    value = ArrayField(
        models.TextField(),
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["index"]

    @classmethod
    def create_default_filters(cls, session):
        default_types = {
            BulkEditSessionType.CASE: PinnedFilterType.DEFAULT_FOR_CASE,
        }.get(session.session_type)

        if not default_types:
            raise NotImplementedError(f"{session.session_type} default pinned filters not yet supported")

        for index, filter_type in enumerate(default_types):
            cls.objects.create(
                session=session,
                index=index,
                filter_type=filter_type,
            )

    def get_report_filter_class(self):
        from corehq.apps.data_cleaning.filters import (
            CaseOwnersPinnedFilter,
            CaseStatusPinnedFilter,
        )
        return {
            PinnedFilterType.CASE_OWNERS: CaseOwnersPinnedFilter,
            PinnedFilterType.CASE_STATUS: CaseStatusPinnedFilter,
        }[self.filter_type]

    def filter_query(self, query):
        return self.get_report_filter_class().filter_query(query, self)


class BulkEditColumn(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="columns", on_delete=models.CASCADE)
    column_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    index = models.IntegerField(default=0)
    prop_id = models.CharField(max_length=255)  # case property or form question_id
    label = models.CharField(max_length=255)
    data_type = models.CharField(
        max_length=15,
        default=DataType.TEXT,
        choices=DataType.CHOICES,
    )
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["index"]

    @staticmethod
    def get_default_label(prop_id):
        known_labels = {
            'name': _("Name"),
            'owner_name': _('Owner'),
            'opened_on': _("Opened On"),
            'opened_by_username': _("Created By"),
            'modified_on': _("Last Modified On"),
            '@status': _("Status"),
        }
        return known_labels.get(prop_id, prop_id)

    @staticmethod
    def is_system_property(prop_id):
        return prop_id in set(METADATA_IN_REPORTS).difference({
            'name', 'case_name', 'external_id',
        })

    @classmethod
    def create_default_columns(cls, session):
        default_properties = {
            BulkEditSessionType.CASE: (
                'name', 'owner_name', 'opened_on', 'opened_by_username',
                'modified_on', '@status',
            ),
        }.get(session.session_type)

        if not default_properties:
            raise NotImplementedError(f"{session.session_type} default columns not yet supported")

        for index, prop_id in enumerate(default_properties):
            cls.objects.create(
                session=session,
                index=index,
                prop_id=prop_id,
                label=cls.get_default_label(prop_id),
                is_system=cls.is_system_property(prop_id),
            )


class BulkEditRecord(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="records", on_delete=models.CASCADE)
    doc_id = models.CharField(max_length=126, unique=True, db_index=True)  # case_id or form_id
    is_selected = models.BooleanField(default=True)
    calculated_change_id = models.UUIDField(null=True, blank=True)
    calculated_properties = models.JSONField(null=True, blank=True)

    @property
    def has_property_updates(self):
        return self.changes.count() > 0 and (
            self.calculated_change_id is None or self.changes.last().change_id != self.calculated_change_id
        )

    def get_edited_case_properties(self, case):
        """
        Returns a dictionary of properties that have been edited by related BulkEditChanges.
        :param case: CommCareCase
        """
        if case.case_id != self.doc_id:
            raise ValueError("case.case_id doesn't match record.doc_id")

        if not self.has_property_updates:
            return self.calculated_properties or {}

        properties = {}
        for change in self.changes.all():
            properties[change.prop_id] = change.edited_value(case, edited_properties=properties)
        self.calculated_properties = properties
        self.calculated_change_id = self.changes.last().change_id
        self.save()
        return properties


class EditActionType:
    REPLACE = 'replace'
    FIND_REPLACE = 'find_replace'
    STRIP = 'strip'
    COPY_REPLACE = 'copy_replace'
    TITLE_CASE = 'title_case'
    UPPER_CASE = 'upper_case'
    LOWER_CASE = 'lower_case'
    MAKE_EMPTY = 'make_empty'
    MAKE_NULL = 'make_null'
    RESET = 'reset'

    CHOICES = (
        (REPLACE, gettext_lazy("Replace")),
        (FIND_REPLACE, gettext_lazy("Find & Replace")),
        (COPY_REPLACE, gettext_lazy("Copy & Replace")),
        (STRIP, gettext_lazy("Strip Whitespaces")),
        (TITLE_CASE, gettext_lazy("Make Title Case")),
        (UPPER_CASE, gettext_lazy("Make Upper Case")),
        (LOWER_CASE, gettext_lazy("Make Lower Case")),
        (MAKE_EMPTY, gettext_lazy("Make Value Empty")),
        (MAKE_NULL, gettext_lazy("Make Value NULL")),
        (RESET, gettext_lazy("Undo All Edits")),
    )


class BulkEditChange(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="changes", on_delete=models.CASCADE)
    change_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    records = models.ManyToManyField(BulkEditRecord, related_name="changes")
    prop_id = models.CharField(max_length=255)  # case property or form question_id
    action_type = models.CharField(
        max_length=12,
        choices=EditActionType.CHOICES,
    )
    find_string = models.TextField(null=True, blank=True)
    replace_string = models.TextField(null=True, blank=True)
    use_regex = models.BooleanField(default=False)
    copy_from_prop_id = models.CharField(max_length=255)

    class Meta:
        ordering = ["created_on"]

    def edited_value(self, case, edited_properties=None):
        """
        Note: `BulkEditChange`s can be chained/layered. In order to properly chain
        changes, please call BulkEditRecord.get_edited_case_properties(case) to
        properly layer all changes in order.
        """
        edited_properties = edited_properties or {}
        old_value = edited_properties.get(self.prop_id, case.get_case_property(self.prop_id))

        simple_transformations = {
            EditActionType.REPLACE: lambda x: self.replace_string,
            EditActionType.MAKE_EMPTY: lambda x: "",
            EditActionType.MAKE_NULL: lambda x: None,
        }

        if self.action_type in simple_transformations:
            return simple_transformations[self.action_type](old_value)

        if self.action_type == EditActionType.COPY_REPLACE:
            return edited_properties.get(
                self.copy_from_prop_id, case.get_case_property(self.copy_from_prop_id)
            )

        if self.action_type == EditActionType.RESET:
            return case.get_case_property(self.prop_id)

        # all transformations past this point will throw an error if None is passed to it
        if old_value is None:
            return None
        return self._string_edited_value(old_value)

    def _string_edited_value(self, old_value):
        # ensure that the old_value is always a string
        old_value = str(old_value)

        string_regex_transformations = {
            EditActionType.FIND_REPLACE: lambda x: re.sub(
                re.compile(self.find_string), self.replace_string, x
            ),
        }
        if self.use_regex and self.action_type in string_regex_transformations:
            return string_regex_transformations[self.action_type](old_value)

        string_transformations = {
            EditActionType.FIND_REPLACE: lambda x: x.replace(self.find_string, self.replace_string),
            EditActionType.STRIP: str.strip,
            EditActionType.TITLE_CASE: str.title,
            EditActionType.UPPER_CASE: str.upper,
            EditActionType.LOWER_CASE: str.lower,
        }
        if self.action_type in string_transformations:
            return string_transformations[self.action_type](old_value)

        raise UnsupportedActionException(f"edited_value did not recognize action_type {self.action_type}")
