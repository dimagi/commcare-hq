from django.core.management.base import BaseCommand
from corehq import Domain

class Command(BaseCommand):
    help = 'Make sure valid_domains is a superset of owners for all media'

    def handle(self, *args, **options):
        def settify(entity):
            entity = [entity] if not isinstance(entity, list) else entity
            return set(filter(None, entity))

        domains = Domain.get_all()
        for d in domains:
            for m in d.all_media():
                owners, valid_domains = settify(m.owners), settify(m.valid_domains)
                if not valid_domains >= owners:
                    m.valid_domains = list(valid_domains | owners)
                    self.stdout.write("updating media %s: %s => %s" %
                                      (m._id, list(valid_domains), m.valid_domains))
                    m.save()
