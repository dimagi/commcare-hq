# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0038_bootstrap_new_user_buckets'),
    ]

    operations = [
        # for sub adj with switch and related subscription is created by invoicing,
        # hide wrong subscription
        # add right subscription and try to get dates right as well - can just overwrite
    ]
