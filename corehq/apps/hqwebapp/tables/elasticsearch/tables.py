from memoized import memoized

from django_tables2 import tables
from django_tables2.data import TableData
from django_tables2.utils import OrderBy

from corehq.apps.es import ESQuery
from corehq.util.es.elasticsearch import TransportError
from corehq.apps.es.exceptions import ESError
from corehq.apps.reports.exceptions import BadRequestError

from corehq.apps.hqwebapp.tables.elasticsearch.records import BaseElasticRecord


class ElasticTable(tables.Table):
    """
    To use elasticsearch queries with `django_tables2`, please
    make sure the Table passed to your TableView inherits from this class.

    You can then return an unsorted and un-paginated ESQuery in your TableView's
    `get_queryset()` method. Please make sure that the subclass of `ESQuery` is
    compatible with the subclass of `BaseElasticRecord` assigned to
    `record_class` below. For instance, `CaseSearchElasticRecord` is compatible
    with `CaseSearchES`.

    Below is an example setup for a `django_tables2` paginated TableView with
    `ElasticTable`:

    The table:

        class MyCaseTable(ElasticTable):
            record_class = CaseSearchElasticRecord

            name = columns.Column(
                verbose_name=gettext_lazy("Case Name"),
            )
            status = columns.Column(
                accessor="@status",
                verbose_name=gettext_lazy("Status"),
            )
            some_property = columns.Column(
                verbose_name=gettext_lazy("Some Property"),
            )

    ~ If you want to use this table with HTMX (recommended) the class will look like:

        class MyCaseTable(BaseHtmxTable, ElasticTable):
            record_class = CaseSearchElasticRecord

            class Meta(BaseHtmxTable.Meta):
                pass

            ...  # rest of the column configuration


    The TableView:

        class MyCaseTableView(LoginAndDomainMixin, DomainViewMixin, SelectablePaginatedTableView):
            urlname = "..."
            table_class = MyCaseTable

            def get_queryset(self):
                return CaseSearchES().domain(self.domain)

    If using HTMX, you can follow the HTMX table example in the styleguide for the host view.
    """
    record_class = BaseElasticRecord

    def __init__(self, record_kwargs=None, **kwargs):
        data = kwargs.pop('data')
        if not ElasticTableData.validate(data):
            raise ValueError(
                "Please ensure that `data` is a subclass of ESQuery. "
                "Otherwise, do not inherit from ElasticTable."
            )
        data = ElasticTableData(data, record_kwargs or {})
        super().__init__(data=data, **kwargs)


class ElasticTableData(TableData):
    """
    This is a `django_tables2` `TableData` container for processing an
    elasticsearch query with the `ElasticTable` class above.

    You will likely not instantiate this class directly elsewhere. Please see
    the `ElasticTable` class for how to use elasticsearch queries with
    `django_tables2`.
    """

    def __init__(self, query, record_kwargs):
        self.query = query
        self.record_kwargs = record_kwargs
        self._length = None
        super().__init__([])  # init sets self.data to this value

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self._get_records(key.start, key.stop)
        return self._get_records(key, key + 1)[0]

    def _get_records(self, start, stop):
        if stop < start:
            raise ValueError("'stop' must be greater than 'start'")
        size = stop - start
        page_query = self.query.start(start).size(size)
        results = self._get_es_results(page_query)
        self.data = [self.table.record_class(record, self.table.request, **self.record_kwargs)
                     for record in results['hits'].get('hits', [])]
        return self.data

    @staticmethod
    def validate(data):
        """
        Validates `data` (from `ElasticTable`) for use in this container.
        """
        return isinstance(data, ESQuery)

    def set_table(self, table):
        """
        This is called from the __init__ method of `django_tables2`'s `Table` class.
        """
        if not isinstance(table, ElasticTable):
            raise ValueError("The table should be an instance of ElasticTable.")
        if not issubclass(table.record_class, BaseElasticRecord):
            raise ValueError("table.record_class should be a subclass of BaseElasticRecord.")
        super().set_table(table)

    def __len__(self):
        if self._length is None:
            self._length = self._total_records
        return self._length

    @property
    @memoized
    def _total_records(self):
        res = self._get_es_results(self.query.size(0))
        if res is not None:
            return res['hits'].get('total', 0)
        else:
            return 0

    @staticmethod
    def _get_es_results(query):
        try:
            return query.run().raw
        except ESError as e:
            original_exception = e.args[0]
            if isinstance(original_exception, TransportError):
                if hasattr(original_exception.info, "get"):
                    if original_exception.info.get('status') == 400:
                        raise BadRequestError()
            raise e

    def order_by(self, aliases):
        """
        Order the data based on OrderBy aliases (prefixed column names) in the
        table. We first convert the aliases to the column's "accessors" (where appropriate)
        and then pass the list of OrderBy(accessor) values to the ElasticTable's `record_class`
        to sort the query.

        We let the ElasticTable's `record_class` take care of sorting the query because
        each elasticsearch index will have a different approach to sorting,
        depending on whether we are dealing with ESCase, FormES, etc.

        Arguments:
            aliases (an `OrderByTuple` instance from `django_tables2`):
                optionally prefixed names of columns ('-' indicates descending order)
                in order of significance with regard to data ordering.
        """
        accessors = []
        for alias in aliases:
            bound_column = self.table.columns[OrderBy(alias).bare]

            # bound_column.order_by reflects the current ordering applied to
            # the table. As such we need to check the current ordering on the
            # column and use the opposite if it doesn't match the alias prefix.
            if alias[0] != bound_column.order_by_alias[0]:
                accessors += bound_column.order_by.opposite
            else:
                accessors += bound_column.order_by

        self.query = self.table.record_class.get_sorted_query(self.query, accessors)

    @property
    @memoized
    def verbose_name(self):
        """
        The full (singular) name for the data.
        """
        return self.table.record_class.verbose_name

    @property
    @memoized
    def verbose_name_plural(self):
        """
        The full (plural) name for the data.
        """
        return self.table.record_class.verbose_name_plural
