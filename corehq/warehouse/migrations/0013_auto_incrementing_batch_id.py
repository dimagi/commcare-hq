# Generated by Django 1.11.8 on 2018-01-08 12:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('warehouse', '0012_unique_constraints'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='batch',
            name='batch_id',
        ),
        migrations.AddField(
            model_name='batch',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
    ]
