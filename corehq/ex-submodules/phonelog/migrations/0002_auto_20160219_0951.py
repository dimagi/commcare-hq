# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('phonelog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserErrorEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=100, db_index=True)),
                ('xform_id', models.CharField(max_length=50, db_index=True)),
                ('i', models.IntegerField()),
                ('app_id', models.CharField(max_length=50)),
                ('version_number', models.IntegerField()),
                ('date', models.DateTimeField()),
                ('server_date', models.DateTimeField(null=True, db_index=True)),
                ('user_id', models.CharField(max_length=50, db_index=True)),
                ('expr', models.TextField()),
                ('msg', models.TextField()),
                ('session', models.TextField()),
                ('type', models.CharField(max_length=32, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='usererrorentry',
            unique_together=set([('xform_id', 'i')]),
        ),
        migrations.AlterIndexTogether(
            name='usererrorentry',
            index_together=set([('app_id', 'version_number')]),
        ),
    ]
