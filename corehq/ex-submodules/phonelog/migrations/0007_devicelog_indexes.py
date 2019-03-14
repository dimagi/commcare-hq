# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


from corehq.util.django_migrations import AlterIndexIfNotExists


class Migration(migrations.Migration):

    dependencies = [
        ('phonelog', '0006_usererrorentry_context_node'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devicereportentry',
            name='date',
            field=models.DateTimeField(),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='devicereportentry',
            name='type',
            field=models.CharField(max_length=32),
            preserve_default=True,
        ),
        AlterIndexIfNotExists(
            name='devicereportentry',
            index_together=set([('domain', 'device_id'), ('domain', 'date'), ('domain', 'type'), ('domain', 'username')]),
        ),
        # cleanup other index seen locally or on prod
        migrations.RunSQL(
            "DROP INDEX IF EXISTS phonelog_devicereportentry_type",
            "SELECT 1"
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS phonelog_devicereportentry_date",
            "SELECT 1"
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS phonelog_devicereportentry_xform_id_13bf0bbf30cb3e80_like",
            "SELECT 1"
        ),
    ]
