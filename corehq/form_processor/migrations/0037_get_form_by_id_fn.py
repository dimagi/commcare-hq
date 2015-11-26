# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.form_processor.utils.migration import migrate_sql_function


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0036_cleanup_models'),
    ]

    operations = [
        migrate_sql_function('get_form_by_id')
    ]
