# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0033_commcarecasesql_location_uuid'),
    ]

    operations = [
        migrations.RunSQL(
            """
                CREATE INDEX form_processor_commcarecasesql_supply_point_location
                ON form_processor_commcarecasesql(domain, location_uuid) WHERE type = 'supply-point'
            """,
            """
                DROP INDEX form_processor_commcarecasesql_supply_point_location
            """
        )
    ]
