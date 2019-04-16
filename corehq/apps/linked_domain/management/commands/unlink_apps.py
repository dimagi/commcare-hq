from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function
from django.core.management.base import BaseCommand

from couchdbkit import ResourceNotFound
from corehq.apps.app_manager.models import Application
from corehq.apps.linked_domain.models import DomainLink, DomainLinkHistory
from six.moves import input


class Command(BaseCommand):
    help = "Unlinks linked project spaces and converts the downstream app into a standalone app."

    def add_arguments(self, parser):
        parser.add_argument(
            'linked_app_id',
            help='The ID of the downstream app'
        )
        parser.add_argument(
            'linked_domain',
            help='The name of the downstream project space'
        )
        parser.add_argument(
            'master_domain',
            help='The name of the master project space'
        )

    def handle(self, linked_app_id, linked_domain, master_domain, **options):
        try:
            linked_app = Application.get(linked_app_id)
        except ResourceNotFound:
            print('No downstream app found for ID {} '.format(linked_app_id))
            return

        if linked_app.domain != linked_domain:
            print("Project space in the app found from ID {} does not match the linked project space "
                  "that was given.".format(linked_app_id))
            return

        confirm = input(
            """
            Found {} in project space {} linked to project space {}.
            Are you sure you want to un-link these apps? [y/n]
            """.format(linked_app.name, linked_domain, master_domain)
        )
        if confirm.lower() != 'y':
            return

        print('Unlinking apps')
        linked_app.convert_to_application()
        linked_app.save()
        self.hide_domain_link_history(linked_domain, linked_app_id, master_domain)
        print('Operation completed')

    @staticmethod
    def hide_domain_link_history(linked_domain, linked_app_id, master_domain):
        domain_link = DomainLink.all_objects.get(linked_domain=linked_domain, master_domain=master_domain)
        for history in DomainLinkHistory.objects.filter(link=domain_link):
            if history.model_detail['app_id'] == linked_app_id:
                history.hidden = True
                history.save()
        if not DomainLinkHistory.objects.filter(link=domain_link).exists():
            domain_link.deleted = True
            domain_link.save()
