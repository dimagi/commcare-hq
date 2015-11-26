# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0034_location_id_index'),
    ]

    NOOP_REVERSE = 'SELECT 1'
    operations = [
        migrations.RunSQL(
            'DROP INDEX IF EXISTS form_processor_xforminstancesql_form_uuid_12662b9ceadeeecc_like',
            NOOP_REVERSE
        ),
        migrations.RunSQL(
            'DROP INDEX IF EXISTS form_processor_xformattac_attachment_uuid_6d1d0a1eff4ada21_like',
            NOOP_REVERSE
        ),
        migrations.RunSQL(
            'DROP INDEX IF EXISTS form_processor_xformattachmentsql_name_4b9f1b0d840a70bc_like',
            NOOP_REVERSE
        ),
        migrations.RunSQL(
            'DROP INDEX IF EXISTS form_processor_xformoperationsql_xform_id_14e64e95f71c3764_like',
            NOOP_REVERSE
        ),
    ]
