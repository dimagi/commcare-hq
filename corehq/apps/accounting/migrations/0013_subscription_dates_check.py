# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations




class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0012_replace__product_type__with__is_product'),
    ]

    operations = [
        migrations.RunSQL(
            """
            ALTER TABLE accounting_subscription
            ADD CONSTRAINT subscription_dates_check CHECK (date_start <= date_end);
            """,
            reverse_sql="""
            ALTER TABLE accounting_subscription
            DROP CONSTRAINT IF EXISTS subscription_dates_check;
            """,
        ),
    ]
