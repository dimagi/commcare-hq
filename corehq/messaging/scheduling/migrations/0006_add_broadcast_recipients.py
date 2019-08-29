# Generated by Django 1.11.6 on 2017-11-02 12:34

from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0005_timedschedule_start_day_of_week'),
    ]

    operations = [
        migrations.AddField(
            model_name='immediatebroadcast',
            name='recipients',
            field=jsonfield.fields.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='scheduledbroadcast',
            name='recipients',
            field=jsonfield.fields.JSONField(default=list),
        ),
    ]
