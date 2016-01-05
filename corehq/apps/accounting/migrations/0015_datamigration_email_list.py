# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import HqRunPython


def copy_emails_to_email_list(apps, schema_editor):
    BillingContactInfo = apps.get_model('accounting', 'BillingContactInfo')

    for contact_info in BillingContactInfo.objects.all():
        if contact_info.emails:
            contact_info.email_list = contact_info.emails.split(',')
        else:
            contact_info.email_list = []
        contact_info.save()


def copy_email_list_to_emails(apps, schema_editor):
    BillingContactInfo = apps.get_model('accounting', 'BillingContactInfo')

    for contact_info in BillingContactInfo.objects.all():
        if contact_info.email_list:
            contact_info.emails = ','.join(contact_info.email_list)
            contact_info.save()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0014_billingcontactinfo_email_list'),
    ]

    operations = [
        HqRunPython(copy_emails_to_email_list, reverse_code=copy_email_list_to_emails),
    ]
