from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase


class Command(AppMigrationCommandBase):
    chunk_size = 5
    DOMAIN_LIST_FILENAME = 'find_apps_with_person_simple_and_reg_in_case_list-domains.txt'
    DOMAIN_PROGRESS_NUMBER_FILENAME = 'find_apps_with_person_simple_and_reg_in_case_list-progress.txt'

    def migrate_app(self, app_doc):

        with_person_simple_and_registration_action = False
        offending_module = ""

        for module in app_doc['modules']:
            uses_person_simple = 'case_tile_template' in module['case_details']['short'] \
                                 and module['case_details']['short']['case_tile_template'] == 'person_simple'
            defines_registration_action = module['case_list_form']['form_id']

            if defines_registration_action and uses_person_simple:
                with_person_simple_and_registration_action = True
                offending_module = module["name"]

                if 'en' in offending_module:
                    offending_module = offending_module['en']
                break

        if with_person_simple_and_registration_action:
            print(f"{ app_doc['name'] }\t{ app_doc['_id'] }\t{ offending_module }\t{ app_doc['domain']}")
