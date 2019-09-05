# flake8: noqa
# Generated by Django 1.11.20 on 2019-04-05 17:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('linked_domain', '0007_auto_20180215_1434'),
    ]

    operations = [
        migrations.AlterField(
            model_name='domainlinkhistory',
            name='model',
            field=models.CharField(choices=[('app', 'Application'), ('custom_user_data', 'Custom User Data Fields'), ('custom_product_data', 'Custom Product Data Fields'), ('custom_location_data', 'Custom Location Data Fields'), ('roles', 'User Roles'), ('toggles', 'Feature Flags and Previews'), ('case_search_data', 'Case Search Settings')], max_length=128),
        ),
    ]
