# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DomainMigrationProgress',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(default=None, max_length=256)),
                ('migration_slug', models.CharField(default=None, max_length=256)),
                ('migration_status', models.CharField(default=b'not_started', max_length=11, choices=[(b'not_started', b'Not Started'), (b'in_progress', b'In Progress'), (b'complete', b'Complete')])),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='domainmigrationprogress',
            unique_together=set([('domain', 'migration_slug')]),
        ),
    ]
