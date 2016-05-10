# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import cchq_prbac_bootstrap
from corehq.sql_db.operations import HqRunPython

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0030_remove_softwareplan_visibility_trial_internal'),
    ]

    operations = [
        HqRunPython(cchq_prbac_bootstrap),
    ]
