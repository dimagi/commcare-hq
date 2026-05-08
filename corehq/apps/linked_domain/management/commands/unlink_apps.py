from django.core.management.base import BaseCommand

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.models import Application
from corehq.apps.linked_domain.const import MODEL_APP
from corehq.apps.linked_domain.models import DomainLink, DomainLinkHistory


class Command(BaseCommand):
    help = "Unlinks applications in a downstream project space"

    def add_arguments(self, parser):
        parser.add_argument(
            'downstream_app_id',
            help='The ID of the downstream app'
        )
        parser.add_argument(
            'downstream_domain',
            help='The name of the downstream project space'
        )
        parser.add_argument(
            'upstream_domain',
            help='The name of the upstream project space'
        )

    def handle(self, downstream_app_id, downstream_domain, upstream_domain, **options):
        try:
            downstream_app = Application.get(downstream_app_id)
        except ResourceNotFound:
            print('No downstream app found for ID {} '.format(downstream_app_id))
            return

        if downstream_app.domain != downstream_domain:
            print("Project space in the app found from ID {} does not match the downstream project space "
                  "that was given.".format(downstream_app_id))
            return

        confirm = input(
            """
            Found {} in the downstream domain {} linked to {}.
            Are you sure you want to un-link these apps? [y/n]
            """.format(downstream_app.name, downstream_domain, upstream_domain)
        )
        if confirm.lower() != 'y':
            return

        print('Unlinking apps')
        downstream_app = downstream_app.convert_to_application()
        downstream_app.save()
        self.hide_domain_link_history(downstream_domain, downstream_app_id, upstream_domain)
        print('Operation completed')

    @staticmethod
    def hide_domain_link_history(downstream_domain, downstream_app_id, upstream_domain):
        domain_link = DomainLink.all_objects.get(linked_domain=downstream_domain, master_domain=upstream_domain)
        for history in DomainLinkHistory.objects.filter(
            link=domain_link,
            model=MODEL_APP,
        ):
            if history.model_detail['app_id'] == downstream_app_id:
                history.hidden = True
                history.save()
        if not DomainLinkHistory.objects.filter(link=domain_link).exists():
            domain_link.deleted = True
            domain_link.save()
