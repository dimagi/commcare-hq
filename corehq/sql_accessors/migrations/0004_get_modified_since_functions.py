# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0003_get_forms_by_user_id_functions')
    ]

    operations = [
        noop_migration()
    ]
