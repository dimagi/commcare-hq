from typing import Optional, Tuple

from memoized import memoized

from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType


class CouchDbDataCollector:
    """
    This class simplifies getting and filtering data from CouchDB for a specific domain
    """

    def __init__(self, domain, tables=None):
        """
        :param tables: couchdb tables names for the given domain, if not given, then all tables for that domain
        will be saved
        """
        self.domain = domain
        self.tables = {}
        for table in FixtureDataType.by_domain(domain=domain):
            if (tables and table.tag in tables) or not tables:
                self.tables[table.tag] = table.get_id

    @memoized
    def get_data_from_table(self, table_name=None, fields_and_values: Optional[Tuple] = None):
        """
        filters and collects data from the desired table based on fields_and_values

        :param table_name: name of the table the data is supposed to be collected from
        :param fields_and_values: tuple of tuples, used for filtering, each tuple should have 2 elements:
            1st element: column to look for in the data
            2nd element: tuple of values to look for in the column

            e.g.
            (
                ('age', ('7', '14', '21')),
                ('name', ('Mary', 'Steve'))
            )

        :return: list of filtered data collected from the table OR all rows from the table
        """
        if table_name is None and len(self.tables) == 1:
            table_name = list(self.tables.keys())[0]
        elif not table_name:
            raise AttributeError('\'table_name\' must be specified')
        elif table_name not in self.tables:
            raise ValueError('Unknown \'table_name\'')
        records = FixtureDataItem.by_data_type(self.domain, self.tables[table_name])

        if not fields_and_values:
            return records
        values = dict(fields_and_values)

        return [r for r in records if self._is_record_valid(r, values)]

    @memoized
    def get_data_from_table_as_dict(self, key_field, fields_and_values: Optional[Tuple], table_name=None):
        """
        does the same filtering as get_data_from_table, but returns the data in
        form of a dictionary with values of :param key_field as keys
        """
        if key_field not in dict(fields_and_values):
            raise ValueError('\'key_field\'s name must be in \'fields_and_values\'')

        data = {}
        for record in self.get_data_from_table(table_name, fields_and_values):
            rdict = self.records_data_as_dict(record)
            rdict_without_id = {k: v for k, v in rdict.items() if k != key_field}
            data[rdict[key_field]] = rdict_without_id

        return data

    @staticmethod
    def records_data_as_dict(record, fields_to_filter=None):
        """
        transforms FixtureDataItem object into a dictionary
        :param record FixtureDataItem object
        :param fields_to_filter: if not None only desired fields from the record will be returned
        :return: returns record or some of it's fields as dictionary
        """
        record_as_dict = {}
        fields = record.fields
        for field in fields:
            field_list = fields[field].field_list
            value = None if not field_list else field_list[0].field_value
            record_as_dict[field] = value

        if not fields_to_filter:
            return record_as_dict

        return {k: v for k, v in record_as_dict.items() if k in fields_to_filter}

    def _is_record_valid(self, record, values):
        if values:
            fields_values = self.records_data_as_dict(
                record, [x for x in values.keys()]
            )
            if fields_values and self._values_match(fields_values, values):
                return record

        return None

    @staticmethod
    def _values_match(field_values, values):
        return all(field_values[key] in values[key] for key in values)
