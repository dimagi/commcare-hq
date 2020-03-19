import sys

from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.suite_xml.post_process.resources import copy_xform_resource_overrides
from corehq.apps.linked_domain.applications import get_master_app_by_version


class Command(BaseCommand):
    help = """
        For use when creating a new master app for ICDS.

        After running copy_icds_app_1_of_2 on the master domain to create a copy of the master app,
        run this command on all apps linked to that master app.

        Looks up any ResourceOverrides for the given linked app that are tied to the original
        master app's form ids. For any such override, the script creates a new ResourceOverride
        where the pre_id is the unique id of that same form in the master app copy and the
        post_id is the same as the original override.

        This command is necessary until the ICDS apps are pinned to 2.47.4+.
    """

    def add_arguments(self, parser):
        parser.add_argument('linked_domain')
        parser.add_argument('linked_app_id')
        parser.add_argument('original_master_app_id')
        parser.add_argument('original_master_app_version')
        parser.add_argument('copy_master_app_id')
        parser.add_argument('copy_master_app_version')

    def handle(self, linked_domain, linked_app_id, original_master_app_id, original_master_app_version,
               copy_master_app_id, copy_master_app_version, **options):
        domain_link = get_app(linked_domain, linked_app_id).domain_link
        original_master_app = get_master_app_by_version(domain_link,
                                                        original_master_app_id,
                                                        original_master_app_version)
        copy_master_app = get_master_app_by_version(domain_link,
                                                    copy_master_app_id,
                                                    copy_master_app_version)

        if not original_master_app:
            print("Could not find original master app")
            sys.exit(1)

        if not copy_master_app:
            print("Could not find copy of master app")
            sys.exit(1)

        original_map = get_xmlns_unique_id_map(original_master_app)
        copy_map = get_xmlns_unique_id_map(copy_master_app)
        if original_map.keys() != copy_map.keys():
            print("Original and copied master apps contain different xmlnses")
            sys.exit(1)

        # Map original's form unique ids to copy's form unique ids
        id_map = {unique_id: copy_map[xmlns] for xmlns, unique_id in original_map.items()}

        new_overrides = copy_xform_resource_overrides(linked_domain, linked_app_id, id_map)

        print("Complete, created {} new overrides.".format(len(new_overrides)))


def get_xmlns_unique_id_map(app):
    return {f.xmlns: f.unique_id for f in app.get_forms() if f.form_type != 'shadow_form'}
