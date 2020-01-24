from memoized import memoized

from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType


class CouchData:

    def __init__(self, domain, tables=None):
        if not isinstance(tables, tuple):
            raise TypeError('\'tables\' must be a tuple')
        self.domain = domain
        self.tables = {}
        for table in FixtureDataType.by_domain(domain=domain):
            if (tables and table.tag in tables) or not tables:
                self.tables[table.tag] = table.get_id

    @memoized
    def get_data_from_table(self, table_name=None, fields=None, values=None, as_dict=False):
        data = []
        if table_name is None and len(self.tables) == 1:
            table_name = list(self.tables.keys())[0]
        elif not table_name:
            raise AttributeError('\'table_name\' must be specified')
        records = FixtureDataItem.by_data_type(self.domain, self.tables[table_name])
        if not fields:
            return records
        elif not isinstance(fields, tuple):
            raise TypeError('\'fields\' must be a tuple')
        if not isinstance(values, tuple):
            raise TypeError('\'values\' must be a tuple')
        values = self._reassign_values({x[0]: x[1] for x in values})

        for record in records:
            valid_record = self._check_values(record, values)
            invalid = True if not valid_record else False

            if as_dict and not invalid:
                data.append(self.record_to_dict(record))
            elif not invalid:
                data.append(record)

        return data

    @staticmethod
    def record_to_dict(record):
        record_as_dict = {}
        fields = record.fields
        for field in fields:
            field_list = fields[field].field_list
            value = None if not field_list else field_list[0].field_value
            record_as_dict[field] = value

        return record_as_dict

    @memoized
    def as_dict(self, table_name=None, key_field=None, additional_fields=None, values=None):
        if key_field is None:
            key_field = 'food_code'
        if not additional_fields:
            additional_fields = tuple()
        elif not isinstance(additional_fields, tuple):
            raise TypeError('\'additional_fields\' must be a tuple')
        messy_dicts = self.get_data_from_table(
            table_name=table_name, fields=(key_field,) + additional_fields, values=values, as_dict=True
        )
        clean_dicts = {}

        for messy_dict in messy_dicts:
            id_ = messy_dict[key_field]
            if id_ in clean_dicts:
                dict_ = self._get_dict(key_field, messy_dict)
                self._update_dict(clean_dicts[id_], dict_)
            else:
                clean_dicts[id_] = self._get_dict(key_field, messy_dict)

        return [
            [id_, values] for id_, values in clean_dicts.items()
        ]

    @staticmethod
    def _get_dict(id_key, dict_):
        dict_.pop(id_key)
        return dict_

    def _update_dict(self, old_dict, new_dict):
        new_keys = list(new_dict.keys())
        for key in new_keys:
            suffix = self._get_suffix(key, list(old_dict.keys()))
            if suffix == -1:
                old_dict[key] = new_dict
            if suffix == 1:
                old_dict[f'{key}_1'] = old_dict.pop(key)
                old_dict[f'{key}_2'] = new_dict[key]
            else:
                old_dict[f'{key}_{suffix}'] = new_dict[key]

    @staticmethod
    def _get_suffix(name, names):
        names.sort(reverse=True)
        names = [x for x in names]
        for n in names:
            if name == n:
                return 1
            elif n.startswith(name):
                if n[-1].isdigit():
                    return int(n[-1]) + 1

        return -1

    def _check_values(self, record, values):
        if values:
            fields_values = self._get_fields_values_if_fields_exist(
                record, [x for x in values[0].keys()]
            )
            if fields_values and self._values_match(fields_values, values):
                return record

        return False

    @staticmethod
    def _reassign_values(values):
        to_return = []
        keys = list(values.keys())
        length = len(values[keys[0]])
        for r in range(length):
            to_return.append({})
            for key in keys:
                to_return[-1][key] = values[key][r]

        return to_return

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
        for value in values:
            if value == field_values:
                return True

        return False
