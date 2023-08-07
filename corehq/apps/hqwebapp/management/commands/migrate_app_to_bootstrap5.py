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
    flag_changed_javascript_plugins,
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
            help="Specify the exact template name(s) you would like to migrate",
        )
        parser.add_argument(
            '--js_name',
            help="Specify the exact javascript name(s) you would like to migrate",
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
        js_name = options.get('js_name')
        do_re_check = options.get('re_check')

        if not js_name:
            self.stdout.write(f"\n\nMigrating {app_name} templates...")
            app_templates = self.get_templates_for_migration(app_name, template_name, do_re_check)
            self.migrate_files(app_templates, app_name, spec, is_template=True)

        if not template_name:
            self.stdout.write(f"\n\nMigrating {app_name} javascript...")
            app_javascript = self.get_js_files_for_migration(app_name, js_name, do_re_check)
            self.migrate_files(app_javascript, app_name, spec, is_template=False)

    def _get_files_for_migration(self, files, file_name, do_re_check):
        if file_name is not None:
            files = [t for t in files if file_name in str(t)]

        # filter out already migrated bootstrap3 templates
        files = [t for t in files if '/bootstrap3/' not in str(t)]

        if do_re_check:
            self.stdout.write("Re-checking migrated Bootstrap 5 templates only")
            files = [t for t in files if '/bootstrap5/' in str(t)]
        else:
            files = [t for t in files if '/bootstrap5/' not in str(t)]
        return files

    def get_templates_for_migration(self, app_name, template_name, do_re_check):
        app_template_folder = COREHQ_BASE_DIR / "apps" / app_name / "templates" / app_name
        app_templates = [f for f in app_template_folder.glob('**/*') if f.is_file()]
        return self._get_files_for_migration(app_templates, template_name, do_re_check)

    def get_js_files_for_migration(self, app_name, js_name, do_re_check):
        app_static_folder = COREHQ_BASE_DIR / "apps" / app_name / "static" / app_name
        app_js_files = [f for f in app_static_folder.glob('**/*.js') if f.is_file()]
        return self._get_files_for_migration(app_js_files, js_name, do_re_check)

    def migrate_files(self, files, app_name, spec, is_template):
        for file_path in files:
            short_path = self.get_short_path(app_name, file_path, is_template)

            confirm = input(f'\n{HARD_BREAK_LINE}\n\nReady to migrate "{short_path}"? [y/n] ')
            if confirm.lower() != 'y':
                self.stdout.write(f"\tok, skipping {short_path}")
                continue

            self.migrate_single_file(app_name, file_path, spec, is_template)

    def migrate_single_file(self, app_name, file_path, spec, is_template):
        with open(file_path, 'r') as current_file:
            old_lines = current_file.readlines()
            new_lines = []
            has_changes = False
            file_changelog = []

            for line_number, old_line in enumerate(old_lines):
                if is_template:
                    new_line, renames = self.make_template_line_changes(old_line, spec)
                    flags = self.get_flags_in_template_line(old_line, spec)
                else:
                    new_line = old_line  # no replacement changes yet for js files
                    renames = []
                    flags = self.get_flags_in_javascript_line(old_line, spec)
                saved_line, line_changelog = self.confirm_and_get_line_changes(
                    line_number, old_line, new_line, renames, flags
                )
                new_lines.append(saved_line)
                if saved_line != old_line or flags:
                    has_changes = True
                if line_changelog:
                    file_changelog.extend(line_changelog)

            if has_changes:
                self.record_file_changes(file_path, app_name, file_changelog, is_template)
                if '/bootstrap5/' in str(file_path):
                    self.save_re_checked_file_changes(app_name, file_path, new_lines, is_template)
                else:
                    self.split_files_and_refactor(
                        app_name, file_path, old_lines, new_lines, is_template
                    )
            else:
                short_path = self.get_short_path(app_name, file_path, is_template)
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

    def record_file_changes(self, template_path, app_name, changelog, is_template):
        short_path = self.get_short_path(app_name, template_path.parent, is_template)
        readme_directory = Path(settings.BOOTSTRAP_MIGRATION_LOGS_DIR) / short_path
        readme_directory.mkdir(parents=True, exist_ok=True)
        extension = '.html' if is_template else '.js'
        readme_filename = template_path.name.replace(extension, '.md')
        readme_path = readme_directory / readme_filename
        with open(readme_path, 'w') as readme_file:
            readme_file.writelines(changelog)
        self.stdout.write(f"\nRecorded changes to reference later here:"
                          f"\n\t{readme_path}")

    def save_re_checked_file_changes(self, app_name, file_path, changed_lines, is_template):
        short_path = self.get_short_path(app_name, file_path, is_template)
        confirm = input(f'\nSave changes to {short_path}? [y/n] ')
        if confirm == 'y':
            with open(file_path, 'w') as readme_file:
                readme_file.writelines(changed_lines)
            self.stdout.write("\nChanges saved.")
            self.stdout.write("\nNow would be a good time to review changes with git and "
                              "commit before moving on to the next template.")
            input("\nENTER to continue...")
        else:
            self.stdout.write("ok, skipping save...\n\n")

    def split_files_and_refactor(self, app_name, file_path, bootstrap3_lines, bootstrap5_lines, is_template):
        short_path = self.get_short_path(app_name, file_path, is_template)
        confirm = input(f'\nSplit {short_path} into Bootstrap 3 and Bootstrap 5 versions '
                        f'and update references? [y/n] ')
        if confirm == 'y':
            bootstrap3_path, bootstrap5_path = self.get_split_file_paths(file_path)
            bootstrap3_short_path = self.get_short_path(app_name, bootstrap3_path, is_template)
            bootstrap5_short_path = self.get_short_path(app_name, bootstrap5_path, is_template)
            self.stdout.write(f"ok, saving changes..."
                              f"\n\t{bootstrap3_short_path}"
                              f"\n\t{bootstrap5_short_path}\n\n")
            if '/bootstrap5/' not in str(file_path):
                self.save_split_templates(
                    file_path, bootstrap3_path, bootstrap3_lines, bootstrap5_path, bootstrap5_lines
                )
                self.refactor_references(short_path, bootstrap3_short_path, is_template)
                if not is_template:
                    # also check extension-less references for javascript files
                    self.refactor_references(
                        short_path.replace('.js', ''),
                        bootstrap3_short_path.replace('.js', ''),
                        is_template=False
                    )
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

    def refactor_references(self, old_reference, new_reference, is_template):
        self.stdout.write("updating references...")
        found_references = False
        bootstrap5_reference = new_reference.replace("/bootstrap3/", "/bootstrap5/")
        file_types = ["**/*.py", "**/*.html", "**/*.md"]
        if not is_template:
            file_types.append("**/*.js")
        for file_type in file_types:
            for file_path in COREHQ_BASE_DIR.glob(file_type):
                if not file_path.is_file():
                    continue
                with open(file_path, 'r') as file:
                    filedata = file.read()
                use_bootstrap5_reference = "/bootstrap5/" in str(file_path)
                if old_reference in filedata:
                    found_references = True
                    self.stdout.write(f"- replaced reference in {str(file_path)}")
                    with open(file_path, 'w') as file:
                        file.write(filedata.replace(
                            old_reference,
                            bootstrap5_reference if use_bootstrap5_reference else new_reference
                        ))
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
    def get_flags_in_javascript_line(javascript_line, spec):
        return flag_changed_javascript_plugins(javascript_line, spec)

    @staticmethod
    def get_split_file_paths(file_path):
        bootstrap3_folder = file_path.parent / BOOTSTRAP_3
        bootstrap5_folder = file_path.parent / BOOTSTRAP_5
        bootstrap3_folder.mkdir(parents=True, exist_ok=True)
        bootstrap5_folder.mkdir(parents=True, exist_ok=True)
        return bootstrap3_folder / file_path.name, bootstrap5_folder / file_path.name

    @staticmethod
    def get_short_path(app_name, full_path, is_template):
        if is_template:
            replace_path = COREHQ_BASE_DIR / "apps" / app_name / "templates"
        else:
            replace_path = COREHQ_BASE_DIR / "apps" / app_name / "static"
        return str(full_path).replace(
            str(replace_path) + '/',
            ''
        )
