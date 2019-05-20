# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations




class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0056_last_modified_form_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='ledgervalue',
            name='domain',
            field=models.CharField(default=None, null=True, max_length=255),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ledgervalue',
            name='location_id',
            field=models.CharField(default=None, max_length=255, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ledgervalue',
            name='last_modified_form_id',
            field=models.CharField(default=None, max_length=100, null=True),
            preserve_default=True,
        ),
        migrations.RunSQL(
            """
            UPDATE
                form_processor_ledgervalue
            SET
                domain = (
                    SELECT domain FROM form_processor_commcarecasesql
                    WHERE case_id=form_processor_ledgervalue.case_id
                )
            """,
            "SELECT 1"
        ),
        migrations.RunSQL(
            """
            UPDATE
                form_processor_ledgervalue
            SET
                location_id = (
                    SELECT location_id FROM form_processor_commcarecasesql
                    WHERE case_id=form_processor_ledgervalue.case_id
                )
            """,
            "SELECT 1"
        ),
        migrations.AlterField(
            model_name='ledgervalue',
            name='domain',
            field=models.CharField(default=None, null=False, max_length=255),
            preserve_default=True,
        ),
    ]
