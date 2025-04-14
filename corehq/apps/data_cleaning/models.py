import re
import uuid

from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.utils.translation import gettext_lazy, gettext as _

from corehq.apps.es.case_search import (
    case_property_missing,
    exact_case_property_text_query,
)
from dimagi.utils.chunked import chunked

from corehq.apps.case_search.const import METADATA_IN_REPORTS
from corehq.apps.data_cleaning.exceptions import (
    UnsupportedActionException,
    UnsupportedFilterValueException,
)
from corehq.apps.data_cleaning.utils.decorators import retry_on_integrity_error
from corehq.apps.es import CaseSearchES

BULK_OPERATION_CHUNK_SIZE = 1000
MAX_RECORDED_LIMIT = 100000


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
    @retry_on_integrity_error(max_retries=3, delay=0.1)
    def restart_case_session(cls, user, domain_name, case_type):
        with transaction.atomic():
            previous_session = cls.get_active_case_session(user, domain_name, case_type)
            if previous_session:
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
        """
        Add a filter to this session.

        :param prop_id: string - The property ID (e.g., case property)
        :param data_type: DataType - the data type of the property
        :param data_type: FilterMatchType - the type of match to perform
        :param value: string - The value to filter on
        :return: The created BulkEditFilter
        """
        return BulkEditFilter.create_for_session(self, prop_id, data_type, match_type, value)

    def add_column(self, prop_id, label, data_type=None):
        """
        Add a column to this session.

        :param prop_id: string - The property ID (e.g., case property)
        :param label: string - The column label to display
        :param data_type: DataType - Optional. Will be inferred for system props
        :return: The created BulkEditColumn
        """
        return BulkEditColumn.create_for_session(self, prop_id, label, data_type)

    @staticmethod
    def _update_order(related_manager, id_field, provided_ids):
        """
        Updates the ordering of related objects by setting their `index` field.

        :param related_manager: a Django RelatedManager (e.g., self.filters, self.columns)
        :param id_field: string name of the object's unique identifier (e.g., 'filter_id')
        :param provided_ids: list of UUIDs in desired order
        """
        if len(provided_ids) != related_manager.count():
            raise ValueError(
                "The lengths of provided_ids and ALL existing objects do not match. "
                "Please provide a list of ALL existing object ids in the desired order."
            )

        # NOTE: We cast the id_field to a string in the instance map to avoid UUID comparison
        # as the forms will be sending the ids as strings, while the remove_method sends it
        # as UUID objects.
        instance_map = {str(getattr(obj, id_field)): obj for obj in related_manager.all()}
        for index, object_id in enumerate(provided_ids):
            try:
                # We need to cast the object_id to a string to match the instance_map keys
                # in case the provided_ids are UUIDs.
                instance = instance_map[str(object_id)]
            except KeyError:
                raise ValueError(f"Object with {id_field} {object_id} not found.")
            instance.index = index

        related_manager.bulk_update(instance_map.values(), ['index'])

    def update_filter_order(self, filter_ids):
        """
        This updates the order of filters for this session
        :param filter_ids: list of uuids matching filter_id field of BulkEditFilters
        """
        self._update_order(self.filters, 'filter_id', filter_ids)

    def update_column_order(self, column_ids):
        """
        This updates the order of columns for this session
        :param column_ids: list of uuids matching column_id field of BulkEditColumns
        """
        self._update_order(self.columns, 'column_id', column_ids)

    def _delete_and_update_order(self, related_manager, id_field, provided_id):
        """
        Deletes a related object by its unique identifier and reindexes the remaining
        related objects to maintain sequential ordering.

        This is typically used for managing indexed relationships (like filters or columns)
        that use an 'index' field to determine order.

        :param related_manager: A Django RelatedManager (e.g., self.filters, self.columns)
        :param id_field: The name of the unique identifier field (e.g., 'filter_id')
        :param provided_id: The ID of the object to be removed
        """
        related_manager.get(**{id_field: provided_id}).delete()
        remaining_ids = related_manager.values_list(id_field, flat=True)
        self._update_order(related_manager, id_field, remaining_ids)

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    def remove_filter(self, filter_id):
        """
        Remove a BulkEditFilter from this session by its filter_id,
        and update the remaining filters to maintain correct index order.

        :param filter_id: UUID of the BulkEditFilter to remove
        """
        with transaction.atomic():
            self._delete_and_update_order(self.filters, 'filter_id', filter_id)

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    def remove_column(self, column_id):
        """
        Remove a BulkEditColumn from this session by its column_id,
        and update the remaining columns to maintain correct index order.

        :param column_id: UUID of the BulkEditColumn to remove
        """
        with transaction.atomic():
            self._delete_and_update_order(self.columns, 'column_id', column_id)

    def get_queryset(self):
        query = CaseSearchES().domain(self.domain).case_type(self.identifier)
        query = BulkEditFilter.apply_filters_to_query(self, query)
        query = BulkEditPinnedFilter.apply_filters_to_query(self, query)
        return query

    def get_num_selected_records(self):
        return self.records.filter(is_selected=True).count()

    def get_num_edited_records(self):
        return self.records.filter(changes__isnull=False).count()

    def is_record_selected(self, doc_id):
        return BulkEditRecord.is_record_selected(self, doc_id)

    def select_record(self, doc_id):
        return BulkEditRecord.select_record(self, doc_id)

    def deselect_record(self, doc_id):
        return BulkEditRecord.deselect_record(self, doc_id)

    def select_multiple_records(self, doc_ids):
        return BulkEditRecord.select_multiple_records(self, doc_ids)

    def deselect_multiple_records(self, doc_ids):
        return BulkEditRecord.deselect_multiple_records(self, doc_ids)

    def _apply_operation_on_queryset(self, operation):
        """
        Perform a bulk operation on the queryset for this session.
        :param operation: function to apply to each record (takes in doc ids as argument)
        """
        for doc_ids in chunked(
            self.get_queryset().scroll_ids(), BULK_OPERATION_CHUNK_SIZE, list
        ):
            operation(doc_ids)

    def select_all_records_in_queryset(self):
        """
        Select all records in the ESQuery queryset for this session.
        """
        self._apply_operation_on_queryset(lambda doc_ids: self.select_multiple_records(doc_ids))

    def deselect_all_records_in_queryset(self):
        """
        Select all records in the ESQuery queryset for this session.
        """
        self._apply_operation_on_queryset(lambda doc_ids: self.deselect_multiple_records(doc_ids))

    def _get_num_unrecorded(self):
        """
        Return the number of records in the current queryset that do not have an
        associated `BulkEditRecord` object.
        :return: int
        """
        num_unrecorded = 0
        for doc_ids in chunked(
            self.get_queryset().scroll_ids(), BULK_OPERATION_CHUNK_SIZE, list
        ):
            num_unrecorded += len(BulkEditRecord.get_unrecorded_doc_ids(self, doc_ids))
        return num_unrecorded

    def can_select_all(self, table_num_records=None):
        """
        Check that, if all records are selected in the queryset,
        the number of `BulkEditRecords` records will not exceed `MAX_RECORDED_LIMIT`.

        Note: This operation might take a long time if the queryset is large.

        :param table_num_records: int
            The value from `table.paginator.count` in a `DataCleaningTableView`.
            Specifying this can help avoid a potentially expensive query.

        :return: bool - True if select_all_records_in_queryset() can be called without exceeding the limit
        """
        if table_num_records and table_num_records > MAX_RECORDED_LIMIT:
            return False

        num_records = self.records.count()
        if table_num_records and table_num_records + num_records <= MAX_RECORDED_LIMIT:
            return True
        # the most potentially expensive query is below:
        return num_records + self._get_num_unrecorded() <= MAX_RECORDED_LIMIT

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

    @classmethod
    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def create_for_session(cls, session, prop_id, data_type, match_type, value=None):
        index = session.filters.count()
        return BulkEditFilter.objects.create(
            session=session,
            index=index,
            prop_id=prop_id,
            data_type=data_type,
            match_type=match_type,
            value=value,
        )

    @classmethod
    def apply_filters_to_query(cls, session, query):
        xpath_expressions = []
        for custom_filter in session.filters.all():
            query = custom_filter.filter_query(query)
            column_xpath = custom_filter.get_xpath_expression()
            if column_xpath is not None:
                xpath_expressions.append(column_xpath)
        if xpath_expressions:
            query = query.xpath_query(session.domain, " and ".join(xpath_expressions))
        return query

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
            FilterMatchType.IS_EMPTY: lambda q: q.filter(exact_case_property_text_query(self.prop_id, '')),
            FilterMatchType.IS_NOT_EMPTY: lambda q: q.NOT(exact_case_property_text_query(self.prop_id, '')),
            FilterMatchType.IS_MISSING: lambda q: q.filter(case_property_missing(self.prop_id)),
            FilterMatchType.IS_NOT_MISSING: lambda q: q.NOT(case_property_missing(self.prop_id)),
        }
        if self.match_type in filter_query_functions:
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

    @classmethod
    def apply_filters_to_query(cls, session, query):
        for pinned_filter in session.pinned_filters.all():
            query = pinned_filter.filter_query(query)
        return query

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
    def is_system_property(prop_id):
        return prop_id in set(METADATA_IN_REPORTS).difference({
            'name', 'case_name', 'external_id',
        })

    @classmethod
    def create_default_columns(cls, session):
        default_properties = {
            BulkEditSessionType.CASE: (
                'name', 'owner_name', 'date_opened', 'opened_by_username',
                'last_modified', '@status',
            ),
        }.get(session.session_type)

        if not default_properties:
            raise NotImplementedError(f"{session.session_type} default columns not yet supported")

        from corehq.apps.data_cleaning.utils.cases import (
            get_system_property_label,
            get_system_property_data_type,
        )
        for index, prop_id in enumerate(default_properties):
            cls.objects.create(
                session=session,
                index=index,
                prop_id=prop_id,
                label=get_system_property_label(prop_id),
                data_type=get_system_property_data_type(prop_id),
                is_system=cls.is_system_property(prop_id),
            )

    @classmethod
    def create_for_session(cls, session, prop_id, label, data_type=None):
        is_system_property = cls.is_system_property(prop_id)
        from corehq.apps.data_cleaning.utils.cases import get_system_property_data_type
        data_type = get_system_property_data_type(prop_id) if is_system_property else data_type
        return cls.objects.create(
            session=session,
            index=session.columns.count(),
            prop_id=prop_id,
            label=label,
            data_type=data_type or DataType.TEXT,
            is_system=is_system_property,
        )

    @property
    def choice_label(self):
        """
        Returns the human-readable option visible in a select field.
        """
        return self.label if self.label == self.prop_id else f"{self.label} ({self.prop_id})"


class BulkEditRecord(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="records", on_delete=models.CASCADE)
    doc_id = models.CharField(max_length=126, unique=True, db_index=True)  # case_id or form_id
    is_selected = models.BooleanField(default=True)
    calculated_change_id = models.UUIDField(null=True, blank=True)
    calculated_properties = models.JSONField(null=True, blank=True)

    @classmethod
    def is_record_selected(self, session, doc_id):
        return session.records.filter(
            doc_id=doc_id,
            is_selected=True,
        ).exists()

    @classmethod
    def get_unrecorded_doc_ids(cls, session, doc_ids):
        recorded_doc_ids = session.records.filter(
            doc_id__in=doc_ids,
        ).values_list("doc_id", flat=True)
        return list(set(doc_ids) - set(recorded_doc_ids))

    @classmethod
    def select_record(cls, session, doc_id):
        record, _ = cls.objects.get_or_create(
            session=session,
            doc_id=doc_id,
            defaults={'is_selected': True}
        )
        if not record.is_selected:
            record.is_selected = True
            record.save()
        return record

    @classmethod
    @retry_on_integrity_error(max_retries=3, delay=0.1)
    def deselect_record(cls, session, doc_id):
        try:
            record = session.records.get(doc_id=doc_id)
        except cls.DoesNotExist:
            return None

        if record.changes.count() > 0:
            record.is_selected = False
            record.save()
        else:
            record.delete()
            record = None

        return record

    @classmethod
    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def select_multiple_records(cls, session, doc_ids):
        session.records.filter(
            doc_id__in=doc_ids,
            is_selected=False,
        ).update(is_selected=True)

        existing_ids = session.records.filter(
            session=session,
            doc_id__in=doc_ids,
        ).values_list("doc_id", flat=True)

        missing_ids = list(set(doc_ids) - set(existing_ids))
        new_records = [
            cls(session=session, doc_id=doc_id, is_selected=True)
            for doc_id in missing_ids
        ]
        # using ignore_conflicts avoids IntegrityErrors if another
        # process inserts them concurrently:
        cls.objects.bulk_create(new_records, ignore_conflicts=True)

        # re-update any records that might still not be marked if there
        # were any conflicts above...
        session.records.filter(
            doc_id__in=doc_ids,
            is_selected=False,
        ).update(is_selected=True)

    @classmethod
    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def deselect_multiple_records(cls, session, doc_ids):
        # update is_selected to False for all selected records that have changes
        session.records.filter(
            doc_id__in=doc_ids,
            is_selected=True,
            changes__isnull=False,
        ).update(is_selected=False)

        # delete all records that have no changes
        session.records.filter(
            doc_id__in=doc_ids,
            changes__isnull=True,
        ).delete()

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
