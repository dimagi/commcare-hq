from django.core.management import call_command, BaseCommand

pillows = [
    'custom.care_pathways.models.GeographyFluffPillow',
    'custom.care_pathways.models.FarmerRecordFluffPillow',
]

domains = ['care-macf-malawi', 'pathways-india-mis', 'pathways-tanzania', 'care-macf-bangladesh']


class Command(BaseCommand):
    def handle(self, *args, **options):
        for domain in domains:
            for pillow in pillows:
                print "Reindex for {}, {} starting".format(domain, pillow)
                print "./manage.py ptop_fast_reindex_fluff {} {} --noinput".format(domain, pillow)
                call_command('ptop_fast_reindex_fluff', domain, pillow, noinput=True)
                print "Reindex for {}, {} complete\n\n".format(domain, pillow)
