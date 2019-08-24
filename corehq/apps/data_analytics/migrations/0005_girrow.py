
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0004_experienced_threshold'),
    ]

    operations = [
        migrations.CreateModel(
            name='GIRRow',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('month', models.DateField(db_index=True)),
                ('domain_name', models.TextField()),
                ('country', models.TextField(null=True, blank=True)),
                ('sector', models.TextField(null=True, blank=True)),
                ('subsector', models.TextField(null=True, blank=True)),
                ('bu', models.TextField(null=True, blank=True)),
                ('self_service', models.NullBooleanField(default=None)),
                ('test_domain', models.NullBooleanField(default=None)),
                ('start_date', models.DateField()),
                ('device_id', models.TextField(null=True, blank=True)),
                ('wam', models.NullBooleanField(default=None)),
                ('pam', models.NullBooleanField(default=None)),
                ('wams_current', models.PositiveIntegerField()),
                ('active_users', models.PositiveIntegerField()),
                ('using_and_performing', models.PositiveIntegerField()),
                ('not_performing', models.PositiveIntegerField()),
                ('inactive_experienced', models.PositiveIntegerField()),
                ('inactive_not_experienced', models.PositiveIntegerField()),
                ('not_experienced', models.PositiveIntegerField()),
                ('not_performing_not_experienced', models.PositiveIntegerField()),
                ('active_ever', models.PositiveIntegerField()),
                ('possibly_exp', models.PositiveIntegerField()),
                ('ever_exp', models.PositiveIntegerField()),
                ('exp_and_active_ever', models.PositiveIntegerField()),
                ('active_in_span', models.PositiveIntegerField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
