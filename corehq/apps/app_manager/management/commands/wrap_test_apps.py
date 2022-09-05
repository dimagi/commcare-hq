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

    def handle(self, **options):
        for filename in self.filenames:
            should_write = False

            with open(filename, encoding='utf-8') as f:
                doc = json.loads(f.read())

            for m in doc.get("modules", []):
                for f in m.get("forms", []):
                    # Form.wrap
                    if f.get('case_references') == []:
                        del f['case_references']
                        should_write = True

            if should_write:
                with open(filename, 'w') as f:
                    f.write(doc)
                print(f"Rewrote {filename}")
            else:
                print(f"Skipped {filename}")
