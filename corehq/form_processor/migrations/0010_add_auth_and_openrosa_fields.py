# -*- coding: utf-8 -*-

from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0009_add_xform_operation_model_and_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='xforminstancesql',
            name='auth_context',
            field=jsonfield.fields.JSONField(default='null'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='openrosa_headers',
            field=jsonfield.fields.JSONField(default='null'),
            preserve_default=True,
        ),
    ]
