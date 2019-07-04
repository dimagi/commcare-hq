from __future__ import absolute_import, unicode_literals

from django.db import migrations

from corehq.util.django_migrations import noop_migration


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        noop_migration(),
    ]
