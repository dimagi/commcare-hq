# Generated by Django 2.2.25 on 2022-02-03 16:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0009_remove_girrow_wam'),
    ]

    operations = [
        migrations.AddField(
            model_name='maltrow',
            name='last_run_date',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
