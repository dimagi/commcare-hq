from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.app_manager.models import Application
from six.moves import input


class Command(BaseCommand):
    help = "Unlinks linked project spaces and converts the downstream app into a standalone app."

    def add_arguments(self, parser):
        parser.add_argument(
            'master_domain_name',
            help='The name of the master project space'
        )
        # parser.add_argument(
        #     'master_app_name',
        #     help='The name of the master app'
        # )
        parser.add_argument(
            'linked_domain_name',
            help='The name of the linked project space'
        )
        parser.add_argument(
            'linked_app_name',
            help='the name of the linked app'
        )

    # def handle(self, master_domain_name, master_app_name, linked_domain_name, linked_app_name, **options):
    def handle(self, master_domain_name, linked_domain_name, linked_app_name, **options):
        master_domain = Domain.get_by_name(master_domain_name)
        linked_domain = Domain.get_by_name(linked_domain_name)
        if not master_domain:
            print('domain with name "{}" not found'.format(master_domain_name))
            return
        if not linked_domain:
            print('domain with name "{}" not found'.format(linked_domain_name))
            return

        try:
            domain_link = DomainLink.objects.get(
                linked_domain=linked_domain_name, master_domain=master_domain_name
            )
        except DomainLink.DoesNotExist:
            print('No DomainLink found for master project space {} and linked project space {}.'.format(
                master_domain_name, linked_domain_name
            ))
            return

        linked_apps = []
        for app in linked_domain.applications():
            if app.name == linked_app_name and \
                    app.doc_type == 'LinkedApplication' and app.domain_link == domain_link:
                linked_apps.append(app)
        if not linked_apps:
            print('No apps called {} in project space {} found with link to project space {}.'.format(
                linked_app_name, linked_domain_name, master_domain_name
            ))
            return

        print('Found {} linked app(s) to un-link.'.format(len(linked_apps)))
        for app in linked_apps:
            confirm = input(
                "Are you sure you want to unlink the app {} from the master project space {}? (y/n)".format(
                    app.name, master_domain_name
                )
            )
            if confirm.lower() != "y":
                continue

            print('Unlinking app {}'.format(app.name))
            raw_linked_app_doc = Application.get_db().get(app.id)
            del raw_linked_app_doc['master']
            del raw_linked_app_doc['linked_app_translations']
            del raw_linked_app_doc['linked_app_logo_refs']
            del raw_linked_app_doc['uses_master_app_form_ids']
            raw_linked_app_doc['doc_type'] = 'Application'
            Application.get_db().save_doc(raw_linked_app_doc)
            domain_link.deleted = True
            domain_link.save()
            print('Operation completed')
