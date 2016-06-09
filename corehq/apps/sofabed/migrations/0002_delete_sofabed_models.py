# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sofabed', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='caseactiondata',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='caseactiondata',
            name='case',
        ),
        migrations.DeleteModel(
            name='CaseActionData',
        ),
        migrations.RemoveField(
            model_name='caseindexdata',
            name='case',
        ),
        migrations.DeleteModel(
            name='CaseData',
        ),
        migrations.DeleteModel(
            name='CaseIndexData',
        ),
        migrations.DeleteModel(
            name='FormData',
        ),
    ]
