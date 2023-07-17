import textwrap

from django.core.management.base import BaseCommand

from corehq.apps.domain.dbaccessors import iter_all_domains_and_deleted_domains_with_name


class DomainBaseCommand(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_name',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.',
        )

    def handle(self, domain_name, **options):
        domain_objs = list(iter_all_domains_and_deleted_domains_with_name(domain_name))
        if not domain_objs:
            print('domain with name "{}" not found'.format(domain_name))
            return
        if len(domain_objs) > 1:
            print("FYI: There are multiple domain objects for this domain"
                  "and they will all be handled.")

        if not options['noinput']:
            confirm = input(textwrap.dedent(
                self.confirmation_message(domain_name)
            ))
            if confirm != domain_name:
                print("\n\t\tCommand cancelled.")
                return
        print(self.action_message(domain_name))

        for domain_obj in domain_objs:
            assert domain_obj.name == domain_name  # Just to be really sure!
            self.handle_domain(domain_obj)

        print("Operation completed")

    def confirmation_message(self, domain_name):
        raise NotImplementedError('subclasses of DomainBaseCommand must provide a confirmation_message() method')

    def action_message(self, domain_name):
        raise NotImplementedError('subclasses of DomainBaseCommand must provide a action_message() method')

    def handle_domain(self, domain_name):
        raise NotImplementedError('subclasses of DomainBaseCommand must provide a handle_domain() method')
