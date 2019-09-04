# Generated by Django 1.11.14 on 2018-09-27 15:34

from django.db import migrations




class Migration(migrations.Migration):

    dependencies = [
        ('warehouse', '0030_one_synclog_per_user'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='applicationstatusfact',
            unique_together=set([]),
        ),
        migrations.RunSQL(
            """
            CREATE UNIQUE INDEX applicationstatusfact_unique_app_user
            ON warehouse_applicationstatusfact (user_dim_id, COALESCE(app_dim_id, -1))
            """
        )
    ]
