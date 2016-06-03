# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import cchq_prbac_bootstrap


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0034_do_not_email_reminders'),
    ]

    operations = [
        migrations.RunPython(cchq_prbac_bootstrap),
    ]
