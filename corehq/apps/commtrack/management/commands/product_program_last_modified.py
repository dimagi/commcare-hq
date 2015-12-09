from django.core.management.base import BaseCommand
from corehq.apps.programs.models import Program
from corehq.apps.products.models import Product
from dimagi.utils.couch.database import iter_docs
from datetime import datetime

class Command(BaseCommand):
    help = 'Populate last_modified field for products and programs'

    def handle(self, *args, **options):
        self.stdout.write("Processing products...\n")

        relevant_ids = set([r['id'] for r in Product.get_db().view(
            'commtrack/products',
            reduce=False,
        ).all()])

        to_save = []

        for product in iter_docs(Product.get_db(), relevant_ids):
            if 'last_modified' not in product or not product['last_modified']:
                product['last_modified'] = datetime.utcnow().isoformat()
                to_save.append(product)

                if len(to_save) > 500:
                    Product.bulk_save(to_save)
                    to_save = []

        if to_save:
            Product.bulk_save(to_save)

        self.stdout.write("Processing programs...\n")

        relevant_ids = set([r['id'] for r in Program.get_db().view(
            'commtrack/programs',
            reduce=False,
        ).all()])

        to_save = []

        for program in iter_docs(Program.get_db(), relevant_ids):
            if 'last_modified' not in program or not program['last_modified']:
                program['last_modified'] = datetime.utcnow().isoformat()
                to_save.append(program)

                if len(to_save) > 500:
                    Program.get_db().bulk_save(to_save)
                    to_save = []

        if to_save:
            Program.get_db().bulk_save(to_save)
