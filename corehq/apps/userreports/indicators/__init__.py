from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict

from corehq.apps.userreports.util import truncate_value
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from fluff import TYPE_INTEGER


class Column(object):

    def __init__(self, id, datatype, is_nullable=True, is_primary_key=False, create_index=False):
        self.id = id
        self.datatype = datatype
        self.is_nullable = is_nullable
        self.is_primary_key = is_primary_key
        self.create_index = create_index

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

    def __init__(self, display_name, wrapped_spec):
        self.display_name = display_name
        self.wrapped_spec = wrapped_spec


class SingleColumnIndicator(ConfigurableIndicator):

    def __init__(self, display_name, column, wrapped_spec):
        super(SingleColumnIndicator, self).__init__(display_name, wrapped_spec)
        self.column = column

    def get_columns(self):
        return [self.column]


class BooleanIndicator(SingleColumnIndicator):
    """
    A boolean indicator leverages the filter logic and returns "1" if
    the filter is true, or "0" if it is false.
    """

    def __init__(self, display_name, column_id, filter, wrapped_spec):
        super(BooleanIndicator, self).__init__(display_name,
                                               Column(column_id, datatype=TYPE_INTEGER),
                                               wrapped_spec)
        self.filter = filter

    def get_values(self, item, context=None):
        value = 1 if self.filter(item, context) else 0
        return [ColumnValue(self.column, value)]


class RawIndicator(SingleColumnIndicator):
    """
    Pass whatever's in the column through to the database
    """

    def __init__(self, display_name, column, getter, wrapped_spec):
        super(RawIndicator, self).__init__(display_name, column, wrapped_spec)
        self.getter = getter

    def get_values(self, item, context=None):
        return [ColumnValue(self.column, self.getter(item, context))]


class CompoundIndicator(ConfigurableIndicator):
    """
    An indicator that wraps other indicators.
    """

    def __init__(self, display_name, indicators, wrapped_spec):
        super(CompoundIndicator, self).__init__(display_name, wrapped_spec)
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
        super(LedgerBalancesIndicator, self).__init__(spec.display_name, spec)

    def _make_column(self, product_code):
        column_id = '{}_{}'.format(self.column_id, product_code)
        return Column(column_id, TYPE_INTEGER)

    @staticmethod
    def _get_values_by_product(ledger_section, case_id, product_codes, domain):
        """returns a defaultdict mapping product codes to their values"""
        ret = defaultdict(lambda: 0)
        ledgers = LedgerAccessors(domain).get_ledger_values_for_case(case_id)
        for ledger in ledgers:
            if ledger.section_id == ledger_section and ledger.entry_id in product_codes:
                ret[ledger.entry_id] = ledger.stock_on_hand

        return ret

    def get_columns(self):
        return [self._make_column(product_code) for product_code in self.product_codes]

    def get_values(self, item, context=None):
        case_id = self.case_id_expression(item)
        domain = context.root_doc['domain']
        values = self._get_values_by_product(self.ledger_section, case_id, self.product_codes, domain)
        return [ColumnValue(self._make_column(product_code), values[product_code])
                for product_code in self.product_codes]
