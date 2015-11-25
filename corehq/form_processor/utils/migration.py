# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import namedtuple

from django.db import models, migrations
import uuidfield.fields


class ModelField(object):
    def __init__(self, model, name, unique=False, db_index=False, null=False):
        self.name = name
        self.model = model
        self.unique = unique
        self.db_index = db_index
        self.null = null


class ForeignKeyField(ModelField):
    def __init__(self, model, field, constraint, unique=False, db_index=False, null=False):
        self.constraint = constraint
        super(ForeignKeyField, self).__init__(model, field, unique=unique, db_index=db_index, null=null)


def migrate_field_to_uuid(model_name, field_name, unique=False, db_index=False, null=False):
    return migrate_field_with_foreign_keys_to_uuid(ModelField(
        model_name,
        field_name,
        unique=unique,
        db_index=db_index,
        null=False
    ))


def migrate_field_with_foreign_keys_to_uuid(primary_field, foreignkey_fields=None):
    forward = []
    reverse = []
    foreignkey_fields = foreignkey_fields or []
    for field in foreignkey_fields:
        drop = _drop_constraint_sql(field)
        forward.append(drop)
        reverse.append(drop)

    for field in [primary_field] + foreignkey_fields:
        forward.append(_alter_to_uuid_sql_forawd(field))
        reverse.append(_alter_to_uuid_sql_reverse(field))

    for field in foreignkey_fields:
        create = _create_constraint_sql(primary_field, field)
        forward.append(create)
        reverse.append(create)

    return migrations.RunSQL(
        '\n'.join(forward),
        '\n'.join(reverse),
        state_operations=[migrations.AlterField(
            model_name=primary_field.model,
            name=primary_field.name,
            field=uuidfield.fields.UUIDField(
                unique=primary_field.unique,
                max_length=32,
                db_index=primary_field.db_index,
                null=primary_field.null),
            preserve_default=True,
        )]
    )


def _drop_constraint_sql(field):
    return 'ALTER TABLE form_processor_{model} DROP CONSTRAINT "{constraint}";'.format(
        model=field.model, constraint=field.constraint
    )


def _create_constraint_sql(primary, field):
    return '''
        ALTER TABLE "form_processor_{model}" ADD CONSTRAINT "{constraint}"
        FOREIGN KEY ({field}) REFERENCES form_processor_{primary_model}({primary_field}) DEFERRABLE INITIALLY DEFERRED;
        '''.format(
            model=field.model,
            constraint=field.constraint,
            field=field.name,
            primary_model=primary.model,
            primary_field=primary.name
    )


def _alter_to_uuid_sql_forawd(field):
    return 'ALTER TABLE "form_processor_{model}" ALTER COLUMN "{field}" TYPE uuid USING {field}::uuid;'.format(
        model=field.model, field=field.name
    )


def _alter_to_uuid_sql_reverse(field):
    return 'ALTER TABLE "form_processor_{model}" ALTER COLUMN "{field}" TYPE varchar(255);'.format(
        model=field.model, field=field.name
    )

