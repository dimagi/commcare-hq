from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from abc import ABCMeta, abstractmethod

import six

from corehq.apps.userreports.datatypes import DATA_TYPE_INTEGER, DataTypeProperty
from corehq.apps.userreports.indicators import Column
from dimagi.ext import jsonobject


class ColumnAdapater(six.with_metaclass(ABCMeta, object)):
    config_spec = jsonobject.JsonObject

    def __init__(self, db_column):
        self.db_column = db_column
        self.properties = self.config_spec.wrap(db_column.config_params)

    @abstractmethod
    def get_datatype(self):
        pass


PRIMARY_COLUMN_TYPE_REFERENCE = 'reference'
PRIMARY_COLUMN_TYPE_CONSTANT = 'constant'
PRIMARY_COLUMN_TYPE_SQL = 'sql_statement'
PRIMARY_COLUMN_TYPE_CHOICES = (
    (PRIMARY_COLUMN_TYPE_REFERENCE, _('Reference')),
    (PRIMARY_COLUMN_TYPE_CONSTANT, _('Constant')),
    (PRIMARY_COLUMN_TYPE_SQL, _('SQL Statement')),
)


class PrimaryColumnAdapter(six.with_metaclass(ABCMeta, ColumnAdapater)):

    @staticmethod
    def from_db_column(db_column):
        type_to_class_mapping = {
            PRIMARY_COLUMN_TYPE_REFERENCE: ReferenceColumnAdapter,
            PRIMARY_COLUMN_TYPE_CONSTANT: ConstantColumnAdapter,
            PRIMARY_COLUMN_TYPE_SQL: SqlColumnAdapter,
        }
        return type_to_class_mapping[db_column.column_type](db_column)

    def to_ucr_column_spec(self):
        return Column(
            id=self.db_column.column_id,
            datatype=self.get_datatype(),
            # todo: these might need to be configurable some day
            is_nullable=True,
            is_primary_key=False,
            create_index=False,
        )


class ConstantColumnAdapter(PrimaryColumnAdapter):
    def get_datatype(self):
        # todo should be configurable
        return DATA_TYPE_INTEGER


class ReferenceColumnProperties(jsonobject.JsonObject):
    referenced_column = jsonobject.StringProperty(required=True)


class ReferenceColumnAdapter(PrimaryColumnAdapter):
    config_spec = ReferenceColumnProperties

    def get_datatype(self):
        return self.db_column.table_definition.data_source.get_column_by_id(
            self.properties.referenced_column
        ).datatype


class SqlColumnProperties(jsonobject.JsonObject):
    datatype = DataTypeProperty(required=True)
    statement = jsonobject.StringProperty(required=True)
    statement_params = jsonobject.DictProperty()


class SqlColumnAdapter(PrimaryColumnAdapter):
    config_spec = SqlColumnProperties

    def get_datatype(self):
        return self.properties.datatype


class SecondaryColumn(ColumnAdapater):

    @staticmethod
    def from_db_column(db_column):
        # todo
        pass
