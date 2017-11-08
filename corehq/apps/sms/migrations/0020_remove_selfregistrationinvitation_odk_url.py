# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0019_add_new_registration_invitation_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='selfregistrationinvitation',
            name='odk_url',
        ),
    ]
