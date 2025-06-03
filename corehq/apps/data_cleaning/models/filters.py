import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.utils.translation import gettext as _

from corehq.apps.data_cleaning.exceptions import UnsupportedFilterValueException
from corehq.apps.data_cleaning.models.types import (
    BulkEditSessionType,
    DataType,
    FilterMatchType,
    PinnedFilterType,
)
from corehq.apps.data_cleaning.utils.decorators import retry_on_integrity_error
from corehq.apps.es.case_search import (
    case_property_missing,
    exact_case_property_text_query,
)


class BulkEditFilterManager(models.Manager):
    use_for_related_fields = True

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def create_for_session(self, session, prop_id, data_type, match_type, value=None):
        index = session.filters.count()
        return self.create(
            session=session,
            index=index,
            prop_id=prop_id,
            data_type=data_type,
            match_type=match_type,
            value=value,
        )

    def apply_to_query(self, session, query):
        xpath_expressions = []
        for custom_filter in session.filters.all():
            query = custom_filter.filter_query(query)
            column_xpath = custom_filter.get_xpath_expression()
            if column_xpath is not None:
                xpath_expressions.append(column_xpath)
        if xpath_expressions:
            query = query.xpath_query(session.domain, " and ".join(xpath_expressions))
        return query

    def copy_to_session(self, source_session, dest_session):
        for custom_filter in self.filter(session=source_session):
            self.model.objects.create(
                session=dest_session,
                index=custom_filter.index,
                prop_id=custom_filter.prop_id,
                data_type=custom_filter.data_type,
                match_type=custom_filter.match_type,
                value=custom_filter.value,
            )


class BulkEditFilter(models.Model):
    session = models.ForeignKey("data_cleaning.BulkEditSession", related_name="filters", on_delete=models.CASCADE)
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

    objects = BulkEditFilterManager()

    class Meta:
        ordering = ["index"]

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


class BulkEditPinnedFilterManager(models.Manager):
    use_for_related_fields = True

    def create_session_defaults(self, session):
        default_types = {
            BulkEditSessionType.CASE: PinnedFilterType.DEFAULT_FOR_CASE,
        }.get(session.session_type)

        if not default_types:
            raise NotImplementedError(f"{session.session_type} default pinned filters not yet supported")

        for index, filter_type in enumerate(default_types):
            self.create(
                session=session,
                index=index,
                filter_type=filter_type,
            )

    def apply_to_query(self, session, query):
        for pinned_filter in session.pinned_filters.all():
            query = pinned_filter.filter_query(query)
        return query

    def copy_to_session(self, source_session, dest_session):
        for pinned_filter in self.filter(session=source_session):
            self.model.objects.create(
                session=dest_session,
                index=pinned_filter.index,
                filter_type=pinned_filter.filter_type,
                value=pinned_filter.value,
            )


class BulkEditPinnedFilter(models.Model):
    session = models.ForeignKey(
        "data_cleaning.BulkEditSession", related_name="pinned_filters", on_delete=models.CASCADE
    )
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

    objects = BulkEditPinnedFilterManager()

    class Meta:
        ordering = ["index"]

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
