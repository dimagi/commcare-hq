# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import HqRunPython


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0002_bootstrap'),
    ]

    operations = {
        HqRunPython(noop),
    }
