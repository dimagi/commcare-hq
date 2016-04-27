from collections import defaultdict
from corehq.apps.commtrack.models import StockState
from corehq.apps.userreports.sql import truncate_value
from fluff import TYPE_INTEGER


class Column(object):
    def __init__(self, id, datatype, is_nullable=True, is_primary_key=False):
        self.id = id
        self.datatype = datatype
        self.is_nullable = is_nullable
        self.is_primary_key = is_primary_key

    @property
    def database_column_name(self):
        """
        Column name going into the database - needs to be truncated according to db limitations
        """
        return truncate_value(self.id)

    def __repr__(self):
        return "Column('{}', '{}')".format(self.id, self.datatype)


class ColumnValue(object):

    def __init__(self, column, value):
        self.column = column
        self.value = value

    def __repr__(self):
        return "ColumnValue({}, {})".format(self.column.id, self.value)


class ConfigurableIndicatorMixIn(object):

    def get_columns(self):
        raise NotImplementedError()

    def get_values(self, item, context=None):
        raise NotImplementedError()


class ConfigurableIndicator(ConfigurableIndicatorMixIn):

    def __init__(self, display_name):
        self.display_name = display_name


class SingleColumnIndicator(ConfigurableIndicator):

    def __init__(self, display_name, column):
        super(SingleColumnIndicator, self).__init__(display_name)
        self.column = column

    def get_columns(self):
        return [self.column]


class BooleanIndicator(SingleColumnIndicator):
    """
    A boolean indicator leverages the filter logic and returns "1" if
    the filter is true, or "0" if it is false.
    """

    def __init__(self, display_name, column_id, filter):
        super(BooleanIndicator, self).__init__(display_name, Column(column_id, datatype=TYPE_INTEGER))
        self.filter = filter

    def get_values(self, item, context=None):
        value = 1 if self.filter(item, context) else 0
        return [ColumnValue(self.column, value)]


class RawIndicator(SingleColumnIndicator):
    """
    Pass whatever's in the column through to the database
    """
    def __init__(self, display_name, column, getter):
        super(RawIndicator, self).__init__(display_name, column)
        self.getter = getter

    def get_values(self, item, context=None):
        return [ColumnValue(self.column, self.getter(item, context))]


class CompoundIndicator(ConfigurableIndicator):
    """
    An indicator that wraps other indicators.
    """
    def __init__(self, display_name, indicators):
        super(CompoundIndicator, self).__init__(display_name)
        self.indicators = indicators

    def get_columns(self):
        return [c for ind in self.indicators for c in ind.get_columns()]

    def get_values(self, item, context=None):
        return [val for ind in self.indicators for val in ind.get_values(item, context)]


class LedgerBalancesIndicator(ConfigurableIndicator):
    def __init__(self, spec):
        self.product_codes = spec.product_codes
        self.column_id = spec.column_id
        self.ledger_section = spec.ledger_section
        self.case_id_expression = spec.get_case_id_expression()
        super(LedgerBalancesIndicator, self).__init__(spec.display_name)

    def _make_column(self, product_code):
        column_id = '{}_{}'.format(self.column_id, product_code)
        return Column(column_id, TYPE_INTEGER)

    @staticmethod
    def _get_values_by_product(ledger_section, case_id, product_codes):
        """returns a defaultdict mapping product codes to their values"""
        values_by_product = StockState.objects.filter(
            section_id=ledger_section,
            case_id=case_id,
            sql_product__code__in=product_codes,
        ).values_list('sql_product__code', 'stock_on_hand')
        return defaultdict(lambda: 0, values_by_product)

    def get_columns(self):
        return map(self._make_column, self.product_codes)

    def get_values(self, item, context=None):
        case_id = self.case_id_expression(item)
        values = self._get_values_by_product(self.ledger_section, case_id, self.product_codes)
        return [ColumnValue(self._make_column(product_code), values[product_code])
                for product_code in self.product_codes]
