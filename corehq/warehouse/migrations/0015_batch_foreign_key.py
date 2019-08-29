# Generated by Django 1.11.8 on 2018-01-15 08:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('warehouse', '0014_batch_dag_slug'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='commitrecord',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='applicationstatusfact',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='domaindim',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='domainstagingtable',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='formfact',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='formstagingtable',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='groupdim',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='groupstagingtable',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='locationdim',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='locationstagingtable',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='locationtypestagingtable',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='synclogstagingtable',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='userdim',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='usergroupdim',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='userlocationdim',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='userstagingtable',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='applicationstagingtable',
            name='batch',
        ),
        migrations.RemoveField(
            model_name='applicationdim',
            name='batch',
        )
    ]
