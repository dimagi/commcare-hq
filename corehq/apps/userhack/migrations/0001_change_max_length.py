# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators

def forwards_func(apps, schema_editor):
    schema_editor.execute("ALTER TABLE auth_user ALTER COLUMN username TYPE character varying(128)")

class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            forwards_func,
        ),
    ]

