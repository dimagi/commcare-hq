# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import absolute_import
from django.db import migrations



def noop(*args, **kwargs):
    pass


def assert_rule_migration_complete(apps, schema_editor):
    AutomaticUpdateRule = apps.get_model('data_interfaces', 'AutomaticUpdateRule')
    if AutomaticUpdateRule.objects.filter(migrated=False).count() > 0:
        raise RuntimeError("""
            If you are receiving this error in a Dimagi production environment,
            it is unexpected.

            Otherwise, you have unmigrated AutomaticUpdateRules. You can migrate them
            by checking out tag `rule-migration` and running:

                python manage.py migrate_rules
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0017_alter_domaincaserulerun'),
    ]

    operations = [
        migrations.RunPython(assert_rule_migration_complete, reverse_code=noop),
    ]
