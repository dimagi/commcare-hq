# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.util.migration import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0037_get_form_by_id_fn'),
    ]

    operations = [
        noop_migration()
    ]
