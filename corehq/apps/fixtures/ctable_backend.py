from couchdbkit import ResourceNotFound
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from ctable.backends import CtableBackend, CompatibilityException
from dimagi.utils.couch.bulk import CouchTransaction
from django.utils.translation import ugettext as _


class CouchFixtureBackend(CtableBackend):

    def write_rows(self, rows, mapping):
        self.init_data_type(mapping)

        key_columns = mapping.key_columns
        for row_dict in rows:
            self.upsert(mapping, row_dict, key_columns)

    def init_data_type(self, mapping):
        data_type = self.get_data_type(mapping)
        if data_type:
            errors = self.check_mapping(mapping, data_type=data_type)['errors']
            if errors:
                raise CompatibilityException(errors)

            self.add_fields(mapping, data_type)
        else:
            data_type = FixtureDataType(_id=self.get_data_type_id(mapping),
                                        domain=mapping.domains[0],
                                        tag=mapping.name,
                                        name=mapping.name)
            self.add_fields(mapping, data_type)

    def check_mapping(self, mapping, data_type=None):
        errors = []
        warnings = []
        if not data_type:
            data_type = self.get_data_type(mapping)

        if data_type:
            fields = set(data_type.fields)
            mapping_columns = {c.name for c in mapping.columns}
            for name in fields:
                if name in mapping_columns:
                    mapping_columns.remove(name)
                else:
                    warnings.append(_('Field exists in FixtureDataType but not in mapping: %(column)s') % {'column': name})

            for col in mapping.key_columns:
                if col not in fields:
                    mapping_columns.remove(col)
                    errors.append(_('Key column exists in mapping but not in FixtureDataType: %(column)s') % {'column': col})

            for col in mapping_columns:
                warnings.append(_('Field exists in mapping but not in FixtureDataType: %(column)s') % {'column': col})

        return {'errors': errors, 'warnings': warnings}

    def clear_all_data(self, mapping):
        data_type = self.get_data_type(mapping)
        if data_type:
            with CouchTransaction() as transaction:
                data_type.recursive_delete(transaction)

    def add_fields(self, mapping, data_type):
        fields = data_type.fields
        for col in mapping.columns:
            if col.name not in fields:
                data_type.fields.append(col.name)

        data_type.save()

    def upsert(self, mapping, row_dict, key_columns):
        keys = [str(row_dict[k]) for k in key_columns]
        item_id = 'CtableFixtureItem_%s' % '_'.join(keys)
        try:
            item = FixtureDataItem.get(item_id)
        except ResourceNotFound:
            item = FixtureDataItem(_id=item_id,
                                   domain=mapping.domains[0],
                                   data_type_id=self.get_data_type_id(mapping),
                                   sort_key=5)  # where does this come from?

        for field, value in row_dict.items():
            item.fields[field] = value

        item.save()

    def get_data_type_id(self, mapping):
        return 'CtableFixtureType_%s' % mapping.table_name

    def get_data_type(self, mapping):
        try:
            return FixtureDataType.get(self.get_data_type_id(mapping))
        except ResourceNotFound:
            return None
