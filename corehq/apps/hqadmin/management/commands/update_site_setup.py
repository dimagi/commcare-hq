from __future__ import absolute_import
from __future__ import print_function
from django.core.management.base import BaseCommand, CommandError
from django.contrib.sites.models import Site
from django.conf import settings


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'site_address',
            help="the new site address that should be used. This would get set in the site objects name "
                 "and domain."
        )
        parser.add_argument(
            '--skip-checks',
            action='store_true',
            default=False,
            help="If you are sure of what you are doing and want to skip checks to ensure safe update."
        )

    def handle(self, site_address, *args, **options):
        if not options['skip_checks']:
            if settings.SITE_ID != 1:
                raise CommandError("SITE ID under settings expected to have value 1 since only one object is "
                                   "expected")
            sites_count = Site.objects.count()
            if sites_count != 1:
                raise CommandError("Expected to have only one object added by Site during setup but currently "
                                   "its %s " % Site.objects.count())
            site_object = Site.objects.first()
            if site_object.name != "example.com" and site_object.domain != "example.com":
                raise CommandError(
                    """
                       Expected the present site object to have dummy example values.
                       They were probably modified and needs to be rechecked.
                       Current Values, name -> {name}, domain -> {domain}
                    """.format(name=site_object.name, domain=site_object.domain)
                )

            if site_object.name == site_object.domain == site_address:
                print('Site object with the expect name and domain already set.')
                print('No update made.')
                return

        site_object = Site.objects.first()
        site_object.name = site_address
        site_object.domain = site_address
        site_object.save()

        Site.objects.clear_cache()

        site_object = Site.objects.first()
        print('Updated!')
        print('Site object now is name -> {name}, domain -> {domain}'.format(
            name=site_object.name,
            domain=site_object.domain
        ))
