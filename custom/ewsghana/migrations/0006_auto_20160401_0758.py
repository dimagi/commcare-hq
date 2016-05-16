# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ewsghana', '0005_auto_20151204_2142'),
    ]

    operations = [
        migrations.DeleteModel(
            name='EWSMigrationProblem',
        ),
        migrations.DeleteModel(
            name='EWSMigrationStats',
        ),
    ]
