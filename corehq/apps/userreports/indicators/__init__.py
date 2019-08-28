
from datetime import date, timedelta

import six

from fluff import TYPE_DATE, TYPE_INTEGER, TYPE_SMALL_INTEGER

from corehq.apps.userreports.indicators.utils import get_values_by_product
from corehq.apps.userreports.util import truncate_value


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
        Returns bytes
        """
        # we have to explicitly truncate the column IDs otherwise postgres will do it
        # and will choke on them if there are duplicates: http://manage.dimagi.com/default.asp?175495
        return truncate_value(self.id).encode('utf-8')

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
    column_datatype = TYPE_INTEGER

    def __init__(self, display_name, column_id, filter, wrapped_spec):
        super(BooleanIndicator, self).__init__(display_name,
                                               Column(column_id, datatype=self.column_datatype),
                                               wrapped_spec)
        self.filter = filter

    def get_values(self, item, context=None):
        value = 1 if self.filter(item, context) else 0
        return [ColumnValue(self.column, value)]


class SmallBooleanIndicator(BooleanIndicator):
    column_datatype = TYPE_SMALL_INTEGER


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
    column_datatype = TYPE_INTEGER
    default_value = 0

    def __init__(self, spec):
        self.product_codes = spec.product_codes
        self.column_id = spec.column_id
        self.ledger_section = spec.ledger_section
        self.case_id_expression = spec.get_case_id_expression()
        super(LedgerBalancesIndicator, self).__init__(spec.display_name, spec)

    def _make_column(self, product_code):
        column_id = '{}_{}'.format(self.column_id, product_code)
        return Column(column_id, self.column_datatype)

    def _get_values_by_product(self, domain, case_id):
        return get_values_by_product(domain, case_id, self.ledger_section, self.product_codes)

    def get_columns(self):
        return [self._make_column(product_code) for product_code in self.product_codes]

    def get_values(self, item, context=None):
        case_id = self.case_id_expression(item)
        domain = context.root_doc['domain']
        values = self._get_values_by_product(domain, case_id)
        return [
            ColumnValue(self._make_column(product_code), values.get(product_code, self.default_value))
            for product_code in self.product_codes
        ]


class DueListDateIndicator(LedgerBalancesIndicator):
    column_datatype = TYPE_DATE
    default_value = date(1970, 1, 1)

    def _get_values_by_product(self, domain, case_id):
        unix_epoch = date(1970, 1, 1)
        values_by_product = super(DueListDateIndicator, self)._get_values_by_product(domain, case_id)
        return {
            product_code: unix_epoch + timedelta(days=value)
            for product_code, value in six.iteritems(values_by_product)
        }
