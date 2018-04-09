from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Migrates all rules to use the new models"

    def get_queryset(self):
        return AutomaticUpdateRule.objects.filter(migrated=False)

    def handle(self, **options):
        print('Migrating %s rules...' % self.get_queryset().count())

        for rule in self.get_queryset():
            rule.migrate()

        print('Done. %s rules left unmigrated' % self.get_queryset().count())
