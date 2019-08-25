# -*- coding: utf-8 -*-

from django.db import migrations


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
