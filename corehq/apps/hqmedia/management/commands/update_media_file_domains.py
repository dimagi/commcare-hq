from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = 'Make sure valid_domains is a superset of owners for all media'

    def handle(self, **options):
        def settify(entity):
            entity = [entity] if not isinstance(entity, list) else entity
            return set([_f for _f in entity if _f])

        domains = Domain.get_all()
        for d in domains:
            for m in d.all_media():
                owners, valid_domains, sharers = \
                    settify(m.owners), settify(m.valid_domains), settify(m.shared_by)
                new_valid_domains = valid_domains.copy()

                if not new_valid_domains >= owners:
                    new_valid_domains |= owners
                if not new_valid_domains >= sharers:
                    new_valid_domains |= sharers

                if valid_domains != new_valid_domains:
                    m.valid_domains = list(new_valid_domains)
                    self.stdout.write("updating media %s: %s => %s" %
                                      (m._id, list(valid_domains), m.valid_domains))
                    m.save()
