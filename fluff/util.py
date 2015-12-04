# -*- coding: UTF-8 -*-
import logging
import datetime
import sqlalchemy
from .const import TYPE_DATE, TYPE_DATETIME, TYPE_INTEGER, TYPE_STRING, TYPE_DECIMAL

logger = logging.getLogger('fluff')

metadata = sqlalchemy.MetaData()


def get_indicator_model(name, indicator_doc):
    columns = [
        sqlalchemy.Column(
            'doc_id',
            sqlalchemy.Unicode(255),
            nullable=False,
            primary_key=True),
        sqlalchemy.Column(
            'date',
            sqlalchemy.Date,
            nullable=False,
            primary_key=True),
    ]

    try:
        flat_fields = indicator_doc._flat_fields
        for flat_name in flat_fields.keys():
            columns.append(sqlalchemy.Column(
                flat_name,
                sqlalchemy.String,
                nullable=True
            ))
    except AttributeError:
        pass

    group_types = indicator_doc.get_group_types()
    for group_name in indicator_doc.get_group_names():
        columns.append(sqlalchemy.Column(
            group_name,
            get_column_type(group_types[group_name]),
            nullable=False,
            primary_key=True
        ))

    calculators = indicator_doc._calculators
    for calc_name in sorted(calculators.keys()):
        for emitter_name in calculators[calc_name]._fluff_emitters:
            col_name = '{0}_{1}'.format(calc_name, emitter_name)
            columns.append(sqlalchemy.Column(
                col_name,
                sqlalchemy.Integer,
                nullable=True,
            ))

    return sqlalchemy.Table('fluff_{0}'.format(name), metadata, *columns)


def get_column_type(data_type):
    if data_type == TYPE_DATE:
        return sqlalchemy.Date
    if data_type == TYPE_DATETIME:
        return sqlalchemy.DateTime
    if data_type == TYPE_INTEGER:
        return sqlalchemy.Integer
    if data_type == TYPE_DECIMAL:
        return sqlalchemy.Numeric(precision=64, scale=16)
    if data_type == TYPE_STRING:
        return sqlalchemy.Unicode(255)

    raise Exception('Enexpected type: {0}'.format(data_type))


def default_null_value_placeholder(data_type):
    if data_type == "string":
        return '__none__'
    elif data_type == "integer":
        return 1618033988  # see http://en.wikipedia.org/wiki/Golden_ratio
    elif data_type == "date":
        return datetime.date.min
    elif data_type == 'datetime':
        return datetime.datetime.min
    else:
        raise Exception("Unexpected type", data_type)
