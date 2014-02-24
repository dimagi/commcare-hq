from optparse import make_option
from django.contrib.auth.models import User
from django.core.management import BaseCommand


class Command(BaseCommand):
    args = '<domain>'
    help = ('Checks all forms in a domain to make sure their cases were properly updated.')

    option_list = BaseCommand.option_list + (
        make_option('-n', '--name',
            help="Name of new db."),
        )

    def handle(self, *args, **options):
        newdb = options.get('name')
        for user in User.objects.all():
            user.save(using=newdb)