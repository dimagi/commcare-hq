# Generated by Django 4.2.15 on 2024-10-04 14:21

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0071_rm_user_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='invitation',
            name='supply_point',
        ),
    ]
