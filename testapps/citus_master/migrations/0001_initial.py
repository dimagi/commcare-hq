# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

import settings


def _add_worker_node_ops():
    for db in settings.DATABASES.values():
        if db.get('ROLE', None) == 'citus_worker':
            host = db.get('CITUS_NODE_NAME', db['HOST'])
            yield migrations.RunSQL("SELECT * from master_add_node('{}', {})".format(host, db['PORT']))


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS citus;"),
    ] + list(_add_worker_node_ops())
