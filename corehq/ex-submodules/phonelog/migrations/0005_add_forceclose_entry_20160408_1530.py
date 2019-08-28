
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('phonelog', '0004_merge'),
    ]

    operations = [
        migrations.CreateModel(
            name='ForceCloseEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=100, db_index=True)),
                ('xform_id', models.CharField(max_length=50)),
                ('app_id', models.CharField(max_length=50, null=True)),
                ('version_number', models.IntegerField()),
                ('date', models.DateTimeField()),
                ('server_date', models.DateTimeField(null=True)),
                ('user_id', models.CharField(max_length=50, null=True)),
                ('type', models.CharField(max_length=32)),
                ('msg', models.TextField()),
                ('android_version', models.CharField(max_length=32)),
                ('device_model', models.CharField(max_length=32)),
                ('session_readable', models.TextField()),
                ('session_serialized', models.TextField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterIndexTogether(
            name='forcecloseentry',
            index_together=set([('domain', 'server_date')]),
        ),
    ]
