from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand

import corehq
from corehq.apps.hqwebapp.utils.bootstrap import BOOTSTRAP_3, BOOTSTRAP_5
from corehq.apps.hqwebapp.utils.bootstrap.changes import (
    get_spec,
    make_direct_css_renames,
    make_numbered_css_renames,
    make_data_attribute_renames,
    flag_changed_css_classes,
    flag_stateful_button_changes_bootstrap5,
)

COREHQ_BASE_DIR = Path(corehq.__file__).resolve().parent
HARD_BREAK_LINE = "************************************************************************"
SOFT_BREAK_LINE = "- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -"


class Command(BaseCommand):
    help = "This command helps migrate CCHQ applications from Bootstrap 3 to Bootstrap 5."

    def add_arguments(self, parser):
        parser.add_argument('app_name')
        parser.add_argument(
            '--template_name',
            help="Specify the exact template you would like to migrate",
        )
        parser.add_argument(
            '--re-check',
            action='store_true',
            default=False,
            help="Run migration against already split bootstrap 5 files"
        )

    def handle(self, app_name, **options):
        if not settings.BOOTSTRAP_MIGRATION_LOGS_DIR:
            self.stderr.write("\nPlease make sure BOOTSTRAP_MIGRATION_LOGS_DIR is "
                              "set in your localsettings.py before continuing...\n\n")
            return

        spec = get_spec('bootstrap_3_to_5')
        template_name = options.get('template_name')
        do_re_check = options.get('re_check')

        self.stdout.write(f"\n\nMigrating {app_name}...")
        app_templates = self.get_templates_for_migration(app_name, template_name, do_re_check)
        self.migrate_app_templates(app_templates, app_name, spec)

    def get_templates_for_migration(self, app_name, template_name, do_re_check):
        app_template_folder = COREHQ_BASE_DIR / "apps" / app_name / "templates" / app_name
        app_templates = [f for f in app_template_folder.glob('**/*') if f.is_file()]
        if template_name is not None:
            app_templates = [t for t in app_templates if template_name in str(t)]

        # filter out already migrated bootstrap3 templates
        app_templates = [t for t in app_templates if '/bootstrap3/' not in str(t)]

        if do_re_check:
            self.stdout.write("Re-checking migrated Bootstrap 5 templates only")
            app_templates = [t for t in app_templates if '/bootstrap5/' in str(t)]
        else:
            app_templates = [t for t in app_templates if '/bootstrap5/' not in str(t)]

        return app_templates

    def migrate_app_templates(self, app_templates, app_name, spec):
        for template_path in app_templates:
            short_path = self.get_short_path(app_name, template_path)

            confirm = input(f'\n{HARD_BREAK_LINE}\n\nReady to migrate "{short_path}"? [y/n] ')
            if confirm.lower() != 'y':
                self.stdout.write(f"\tok, skipping {short_path}")
                continue

            self.migrate_single_template(app_name, template_path, spec)

    def migrate_single_template(self, app_name, template_path, spec):
        with open(template_path, 'r') as template_file:
            old_lines = template_file.readlines()
            new_lines = []
            has_changes = False
            file_changelog = []

            for line_number, old_line in enumerate(old_lines):
                new_line, renames = self.make_template_line_changes(old_line, spec)
                flags = self.get_flags_in_template_line(old_line, spec)
                saved_line, line_changelog = self.confirm_and_get_line_changes(
                    line_number, old_line, new_line, renames, flags
                )
                new_lines.append(saved_line)
                if saved_line != old_line or flags:
                    has_changes = True
                if line_changelog:
                    file_changelog.extend(line_changelog)

            if has_changes:
                self.record_template_changes(template_path, app_name, file_changelog)
                if '/bootstrap5/' in str(template_path):
                    self.save_re_checked_template_changes(app_name, template_path, new_lines)
                else:
                    self.split_template_and_refactor(
                        app_name, template_path, old_lines, new_lines
                    )
            else:
                short_path = self.get_short_path(app_name, template_path)
                self.stdout.write(f"\nNo changes were needed for {short_path}. Skipping...\n\n")

    def confirm_and_get_line_changes(self, line_number, old_line, new_line, renames, flags):
        changelog = []
        if renames or flags:
            changelog.append(f"\nLine {line_number}:\n")
            self.stdout.write(changelog[-1])
            for flag in flags:
                changelog.append(old_line)
                changelog.append(f"\n{SOFT_BREAK_LINE}\n{flag}\n{SOFT_BREAK_LINE}\n\n")
                self.stdout.write("".join(changelog[-2:]))
                input("ENTER to continue...")
                self.stdout.write('\n')
            if renames:
                changelog.append(f"-{old_line}")
                changelog.append(f"+{new_line}")
                changelog.append("\nRENAMES\n  - " + "\n   - ".join(renames))
                self.stdout.write("".join(changelog[-3:]))
                changelog.append("\n\n")
                confirm = input("\nKeep changes? [y/n] ")
                if confirm.lower() != 'y':
                    changelog.append("CHANGES DISCARDED\n\n")
                    self.stdout.write("ok, discarding changes...")
                    return old_line, changelog
        return new_line, changelog

    def record_template_changes(self, template_path, app_name, changelog):
        short_path = self.get_short_path(app_name, template_path.parent)
        readme_directory = Path(settings.BOOTSTRAP_MIGRATION_LOGS_DIR) / short_path
        readme_directory.mkdir(parents=True, exist_ok=True)
        readme_filename = template_path.name.replace('.html', '.md')
        readme_path = readme_directory / readme_filename
        with open(readme_path, 'w') as readme_file:
            readme_file.writelines(changelog)
        self.stdout.write(f"\nRecorded changes to reference later here:"
                          f"\n\t{readme_path}")

    def save_re_checked_template_changes(self, app_name, template_path, changed_lines):
        short_path = self.get_short_path(app_name, template_path)
        confirm = input(f'\nSave changes to {short_path}? [y/n] ')
        if confirm == 'y':
            with open(template_path, 'w') as readme_file:
                readme_file.writelines(changed_lines)
            self.stdout.write("\nChanges saved.")
            self.stdout.write("\nNow would be a good time to review changes with git and "
                              "commit before moving on to the next template.")
            input("\nENTER to continue...")
        else:
            self.stdout.write("ok, skipping save...\n\n")

    def split_template_and_refactor(self, app_name, template_path, bootstrap3_lines, bootstrap5_lines):
        short_path = self.get_short_path(app_name, template_path)
        confirm = input(f'\nSplit {short_path} into Bootstrap 3 and Bootstrap 5 versions '
                        f'and update references? [y/n] ')
        if confirm == 'y':
            bootstrap3_path, bootstrap5_path = self.get_split_file_paths(template_path)
            bootstrap3_short_path = self.get_short_path(app_name, bootstrap3_path)
            bootstrap5_short_path = self.get_short_path(app_name, bootstrap5_path)
            self.stdout.write(f"ok, saving changes..."
                              f"\n\t{bootstrap3_short_path}"
                              f"\n\t{bootstrap5_short_path}\n\n")
            if '/bootstrap5/' not in str(template_path):
                self.save_split_templates(
                    template_path, bootstrap3_path, bootstrap3_lines, bootstrap5_path, bootstrap5_lines
                )
                self.refactor_references(short_path, bootstrap3_short_path)
            self.stdout.write("\nNow would be a good time to review changes with git and "
                              "commit before moving on to the next template.")
            self.stdout.write("\nSuggested commit message:")
            self.stdout.write(f"bootstrap 3 to 5 auto-migration for {short_path}")
            input("\nENTER to continue...")
        else:
            self.stdout.write("ok, skipping...\n\n")

    @staticmethod
    def save_split_templates(original_path, bootstrap3_path, bootstrap3_lines, bootstrap5_path, bootstrap5_lines):
        original_path.unlink(missing_ok=True)
        with open(bootstrap3_path, 'w') as file:
            file.writelines(bootstrap3_lines)
        with open(bootstrap5_path, 'w') as file:
            file.writelines(bootstrap5_lines)

    def refactor_references(self, old_reference, new_reference):
        self.stdout.write("updating references...")
        found_references = False
        for file_type in ["**/*.py", "**/*.html", "**/*.md"]:
            for file_path in COREHQ_BASE_DIR.glob(file_type):
                if not file_path.is_file():
                    continue
                with open(file_path, 'r') as file:
                    filedata = file.read()

                if old_reference in filedata:
                    found_references = True
                    self.stdout.write(f"- replaced reference in {str(file_path)}")
                    with open(file_path, 'w') as file:
                        file.write(filedata.replace(old_reference, new_reference))
        if not found_references:
            self.stdout.write(f"No references were found for {old_reference}...")

    @staticmethod
    def make_template_line_changes(old_line, spec):
        new_line, renames = make_direct_css_renames(old_line, spec)
        new_line, numbered_renames = make_numbered_css_renames(new_line, spec)
        renames.extend(numbered_renames)
        new_line, attribute_renames = make_data_attribute_renames(new_line, spec)
        renames.extend(attribute_renames)
        return new_line, renames

    @staticmethod
    def get_flags_in_template_line(template_line, spec):
        flags = flag_changed_css_classes(template_line, spec)
        stateful_button_flags = flag_stateful_button_changes_bootstrap5(template_line)
        flags.extend(stateful_button_flags)
        return flags

    @staticmethod
    def get_split_file_paths(file_path):
        bootstrap3_folder = file_path.parent / BOOTSTRAP_3
        bootstrap5_folder = file_path.parent / BOOTSTRAP_5
        bootstrap3_folder.mkdir(parents=True, exist_ok=True)
        bootstrap5_folder.mkdir(parents=True, exist_ok=True)
        return bootstrap3_folder / file_path.name, bootstrap5_folder / file_path.name

    @staticmethod
    def get_short_path(app_name, full_path):
        return str(full_path).replace(
            str(COREHQ_BASE_DIR / "apps" / app_name / "templates") + '/',
            ''
        )
