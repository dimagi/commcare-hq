# Generated by Django 2.2.16 on 2020-10-05 22:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('linked_domain', '0012_auto_20200929_0809'),
    ]

    operations = [
        migrations.AlterField(
            model_name='domainlinkhistory',
            name='model',
            field=models.CharField(choices=[('app', 'Application'),
                                            ('custom_user_data', 'Custom User Data Fields'),
                                            ('custom_product_data', 'Custom Product Data Fields'),
                                            ('custom_location_data', 'Custom Location Data Fields'),
                                            ('roles', 'User Roles'), ('toggles', 'Feature Flags and Previews'),
                                            ('fixture', 'Lookup Table'),
                                            ('case_search_data', 'Case Search Settings'), ('report', 'Report'),
                                            ('data_dictionary', 'Data Dictionary'),
                                            ('dialer_settings', 'Dialer Settings'),
                                            ('otp_settings', 'OTP Pass-through Settings'),
                                            ('hmac_callout_settings', 'Signed Callout'), ('keyword', 'Keyword')],
                                   max_length=128),
        ),
    ]
