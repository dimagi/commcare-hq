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
    def get_data_from_table(self, table_name=None, fields_and_values: Optional[Tuple] = None, as_dict=False):
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

        :param as_dict: determines whether collected data should be returned as dictionary
        :return: list of filtered data collected from the table OR all rows from the table
        """
        data = []
        if table_name is None and len(self.tables) == 1:
            table_name = list(self.tables.keys())[0]
        elif not table_name:
            raise AttributeError('\'table_name\' must be specified')
        elif table_name not in self.tables:
            raise ValueError('Unknown \'table_name\'')
        records = FixtureDataItem.by_data_type(self.domain, self.tables[table_name])

        if not fields_and_values:
            return records
        values = {x[0]: x[1] for x in fields_and_values}

        for record in records:
            if self._is_record_valid(record, values):
                if as_dict:
                    data.append(self.record_to_dict(record))
                else:
                    data.append(record)

        return data

    @staticmethod
    def record_to_dict(record):
        """
        transforms :param record from FixtureDataItem object into a dictionary
        """
        record_as_dict = {}
        fields = record.fields
        for field in fields:
            field_list = fields[field].field_list
            value = None if not field_list else field_list[0].field_value
            record_as_dict[field] = value

        return record_as_dict

    @memoized
    def get_data_from_table_as_dict(self, key_field, table_name=None, fields_and_values: Optional[Tuple] = None):
        """
        does the same filtering as get_data_from_table, but returns the data in
        form of a dictionary with values of :param key_field as keys
        """
        if key_field not in (element[0] for element in fields_and_values):
            raise ValueError('\'key_field\'s name must be in \'fields_and_values\'')
        messy_dicts = self.get_data_from_table(
            table_name=table_name, fields_and_values=fields_and_values, as_dict=True
        )
        clean_dicts = {}

        for messy_dict in messy_dicts:
            clean_dicts[messy_dict[key_field]] = self._get_dict(key_field, messy_dict)

        return clean_dicts

    @staticmethod
    def _get_dict(id_key, dict_):
        tmp_dict = dict_.copy()
        tmp_dict.pop(id_key)

        return tmp_dict

    def _is_record_valid(self, record, values):
        if values:
            fields_values = self._get_fields_values_if_fields_exist(
                record, [x for x in values.keys()]
            )
            if fields_values and self._values_match(fields_values, values):
                return record

        return None

    @staticmethod
    def _get_fields_values_if_fields_exist(record, fields):
        values_for_field = {}
        for field in fields:
            field_ = record.fields.get(field)
            if not field_:
                return False
            elif field_ and field_.field_list:
                values_for_field[field] = field_.field_list[0].field_value

        return values_for_field

    @staticmethod
    def _values_match(field_values, values):
        matching_fields = set()
        for key in values:
            if field_values[key] in values[key]:
                matching_fields.add(key)

        return len(matching_fields) == len(field_values)
