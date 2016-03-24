# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

def migrate_metadata(apps, schema_editor):
    Subscriptions = apps.get_model("accounting", "Subscription")
    for subscription in Subscriptions.objects.all():
        if subscription.service_type == "SELF_SERVICE":
            subscription.service_type = "PRODUCT"
        elif subscription.service_type == "CONTRACTED":
            subscription.service_type = "IMPLEMENTATION"
        if subscription.pro_bono_status == "YES":
            subscription.pro_bono_status = "PRO_BONO"
        elif subscription.pro_bono_status == "NO":
            subscription.pro_bono_status = "FULL_PRICE"
        subscription.save(update_fields=['service_type','pro_bono_status'])



class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0011_subscription_is_hidden_to_ops'),
    ]

    operations = [
        migrations.RunPython(migrate_metadata),
    ]
