import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Import an app from another Commcare instance")

    filenames = [
        "corehq/apps/app_manager/tests/data/cyclical-app.json",
        "corehq/apps/app_manager/tests/data/days_ago_migration.json",
        "corehq/apps/app_manager/tests/data/bad_case_tile_config.json",
        "corehq/apps/app_manager/tests/data/yesno.json",
        "corehq/apps/app_manager/tests/data/suite/call-center.json",
        "corehq/apps/app_manager/tests/data/suite/app_graphing.json",
        "corehq/apps/app_manager/tests/data/suite/sort-only-value.json",
        "corehq/apps/app_manager/tests/data/suite/tiered-select-3.json",
        "corehq/apps/app_manager/tests/data/suite/multi-sort.json",
        "corehq/apps/app_manager/tests/data/suite/app_print_detail.json",
        "corehq/apps/app_manager/tests/data/suite/tiered-select.json",
        "corehq/apps/app_manager/tests/data/suite/shadow_module.json",
        "corehq/apps/app_manager/tests/data/suite/app.json",
        "corehq/apps/app_manager/tests/data/suite/shadow_module_forms_only.json",
        "corehq/apps/app_manager/tests/data/suite/app_video_inline.json",
        "corehq/apps/app_manager/tests/data/suite/suite-advanced.json",
        "corehq/apps/app_manager/tests/data/suite/app_attached_image.json",
        "corehq/apps/app_manager/tests/data/suite/app_case_sharing.json",
        "corehq/apps/app_manager/tests/data/suite/shadow_module_cases.json",
        "corehq/apps/app_manager/tests/data/suite/app_case_tiles.json",
        "corehq/apps/app_manager/tests/data/suite/app_audio_format.json",
        "corehq/apps/app_manager/tests/data/suite/app_case_detail_tabs.json",
        "corehq/apps/app_manager/tests/data/suite/app_case_detail_instances.json",
        "corehq/apps/app_manager/tests/data/suite/app_case_detail_tabs_with_nodesets.json",
        "corehq/apps/app_manager/tests/data/suite/app_fixture_graphing.json",
        "corehq/apps/app_manager/tests/data/suite/owner-name.json",
        "corehq/apps/app_manager/tests/data/suite/app_no_case_sharing.json",
        "corehq/apps/app_manager/tests/data/form_preparation_v2/complex-case-sharing.json",
        "corehq/apps/app_manager/tests/data/form_preparation_v2/subcase-repeat.json",
        "corehq/apps/app_manager/tests/data/form_preparation_v2/gps.json",
        "corehq/apps/app_manager/tests/data/form_preparation_v2/subcase-parent-ref.json",
        "corehq/apps/app_manager/tests/data/form_preparation_v2/multiple_subcase_repeat.json",
        "corehq/apps/app_manager/tests/data/subcase-details.json",
    ]

    def apply_wrap(self, item, wrap_dict):
        should_write = False
        if type(item) == dict:
            should_write = wrap_dict(item) or should_write
            for key in item.keys():
                should_write = self.apply_wrap(item.get(key), wrap_dict) or should_write
            return should_write
        elif type(item) == list:
            for index in range(len(item)):
                should_write = self.apply_wrap(item[index], wrap_dict) or should_write
            return should_write
        return False

    # NavMenuItemMediaMixin.wrap
    @classmethod
    def wrap_media(cls, data):
        should_write = False
        for media_attr in ('media_image', 'media_audio'):
            old_media = data.get(media_attr, None)
            if old_media:
                # Single-language media was stored in a plain string.
                # Convert this to a dict, using a dummy key because we
                # don't know the app's supported or default lang yet.
                if isinstance(old_media, str):
                    should_write = True
                    new_media = {'default': old_media}
                    data[media_attr] = new_media
                elif isinstance(old_media, dict):
                    # Once the media has localized data, discard the dummy key
                    if 'default' in old_media and len(old_media) > 1:
                        should_write = True
                        old_media.pop('default')
        return should_write

    # CustomMonthFilter and NumericFilter
    @classmethod
    def wrap_report_module(cls, data):
        if data.get("doc_type") == "CustomMonthFilter":
            data['start_of_month'] = int(data['start_of_month'])
            if 'period' in data:
                data['period'] = int(data['period'] or 0)
        elif data.get("doc_type") == "NumericFilter":
            data['operand'] = float(data['operand'])
            return True
        return False

    # AdvancedAction subclasses wrap
    @classmethod
    def wrap_action(cls, data):
        if 'parent_tag' in data:
            if data.get("doc_type") == "LoadUpdateAction":
                if data['parent_tag']:
                    data['case_index'] = {
                        'tag': data['parent_tag'],
                        'reference_id': data.get('parent_reference_id', 'parent'),
                        'relationship': data.get('relationship', 'child')
                    }
            elif data.get("doc_type") == "AdvancedOpenCaseAction":
                if data['parent_tag']:
                    index = {
                        'tag': data['parent_tag'],
                        'reference_id': data.get('parent_reference_id', 'parent'),
                        'relationship': data.get('relationship', 'child')
                    }
                    if hasattr(data.get('case_indices'), 'append'):
                        data['case_indices'].append(index)
                    else:
                        data['case_indices'] = [index]
            del data['parent_tag']
            data.pop('parent_reference_id', None)
            data.pop('relationship', None)
            return True
        return False

    def handle(self, **options):
        for filename in self.filenames:
            should_write = False

            with open(filename, encoding='utf-8') as f:
                doc = json.loads(f.read())

            should_write = self.apply_wrap(doc, self.wrap_media) or should_write

            for m in doc.get("modules", []):
                if m.get("doc_type") == "AdvancedModule":
                    # AdvancedModule.wrap
                    if m.get('search_config') == []:
                        m['search_config'] = {}
                        should_write = True
                elif m.get("doc_type") == "ReportModule":
                    should_write = self.apply_wrap(m, self.wrap_report_module) or should_write
                if m.get("search_config"):
                    for prop in m.get("search_config").get("properties", []):
                        # CaseSearchProperty.wrap
                        required = prop.get('required')
                        if required and isinstance(required, str):
                            prop['required'] = {'test': required}
                            should_write = True
                        old_validations = prop.pop('validation', None)  # it was changed to plural
                        if old_validations:
                            prop['validations'] = [{
                                'test': old['xpath'],
                                'text': old['message'],
                            } for old in old_validations if old.get('xpath')]
                            should_write = True
                for f in m.get("forms", []):
                    # Form.wrap
                    if f.get('case_references') == []:
                        del f['case_references']
                        should_write = True
                    if f.get("form_type") == "advanced_form":
                        should_write = self.apply_wrap(f['actions'], self.wrap_action) or should_write
                        # AdvancedForm.wrap
                        load_actions = f.get('actions', {}).get('load_update_cases', [])
                        for action in load_actions:
                            preload = action['preload']
                            if preload and list(preload.values())[0].startswith('/'):
                                action['preload'] = {v: k for k, v in preload.items()}
                                should_write = True

            if should_write:
                with open(filename, 'w') as f:
                    f.write(json.dumps(doc, indent=2))
                print(f"Rewrote {filename}")
            else:
                print(f"Skipped {filename}")
