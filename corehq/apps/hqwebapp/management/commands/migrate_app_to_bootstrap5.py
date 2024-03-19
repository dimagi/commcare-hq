import time
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand

from corehq.apps.hqwebapp.utils.bootstrap import BOOTSTRAP_3, BOOTSTRAP_5
from corehq.apps.hqwebapp.utils.bootstrap.changes import (
    get_spec,
    make_direct_css_renames,
    make_numbered_css_renames,
    make_data_attribute_renames,
    flag_changed_css_classes,
    flag_stateful_button_changes_bootstrap5,
    flag_changed_javascript_plugins,
    flag_path_references_to_split_javascript_files,
    file_contains_reference_to_path,
    replace_path_references,
)
from corehq.apps.hqwebapp.utils.bootstrap.paths import (
    COREHQ_BASE_DIR,
    get_app_template_folder,
    get_app_static_folder,
    get_short_path,
    get_all_template_paths_for_app,
    get_all_javascript_paths_for_app,
)
from corehq.apps.hqwebapp.utils.bootstrap.status import (
    get_completed_templates_for_app,
    get_completed_javascript_for_app,
    get_completed_status,
)
from corehq.apps.hqwebapp.utils.management_command_styling import (
    get_break_line,
    get_style_func,
    Color,
)


class Command(BaseCommand):
    help = "This command helps migrate CCHQ applications from Bootstrap 3 to Bootstrap 5."

    def add_arguments(self, parser):
        parser.add_argument('app_name')
        parser.add_argument(
            '--template_name',
            help="Specify the exact template name(s) you would like to split and migrate",
        )
        parser.add_argument(
            '--js_name',
            help="Specify the exact javascript name(s) you would like to split and migrate",
        )
        parser.add_argument(
            '--re-check',
            action='store_true',
            default=False,
            help="Run migration against already split bootstrap 5 files"
        )
        parser.add_argument(
            '--verify-references',
            action='store_true',
            default=False,
            help="Verify that all references to split files have been updated"
        )

    def handle(self, app_name, **options):
        if not settings.BOOTSTRAP_MIGRATION_LOGS_DIR:
            self.stderr.write("\nPlease make sure BOOTSTRAP_MIGRATION_LOGS_DIR is "
                              "set in your localsettings.py before continuing...\n\n")
            return

        if get_completed_status(app_name):
            self.show_completed_message(app_name)
            return

        spec = get_spec('bootstrap_3_to_5')
        template_name = options.get('template_name')
        js_name = options.get('js_name')
        do_re_check = options.get('re_check')
        verify_references = options.get('verify_references')

        if verify_references:
            self.verify_split_references(app_name)
            return

        if not js_name:
            app_templates = self.get_templates_for_migration(app_name, template_name, do_re_check)
            self.migrate_files(app_templates, app_name, spec, is_template=True)

        if not template_name:
            app_javascript = self.get_js_files_for_migration(app_name, js_name, do_re_check)
            self.migrate_files(app_javascript, app_name, spec, is_template=False)

        self.show_next_steps(app_name)

    def show_next_steps(self, app_name):
        self.clear_screen()
        self.stdout.write(
            self.format_header(f"All done with Step 2 of migrating {app_name}!"),
            style_func=get_style_func(Color.GREEN)
        )
        self.stdout.write("If this is the first time running this command, "
                          "it's recommended to re-run the command\nat least one more "
                          "time in the event of nested dependencies / inheritance "
                          "in split files.\n\n")
        self.stdout.write("After this, please update `bootstrap5_diff_config.json` "
                          "using:\n\n")
        self.stdout.write(f"./mmanage.py build_bootstrap5_diffs --update_app {app_name}\n\n")
        self.stdout.write("Once the changes to that file are committed, you can run:\n")
        self.stdout.write("./mmanage.py build_bootstrap5_diffs\n\n")
        self.stdout.write("Thank you for your dedication to this migration! <3\n\n")
        self.stdout.write("You can also review the next steps here:"
                          "\tcommcarehq.org/styleguide/b5/migration/#update-diffs\n\n\n")

    def show_completed_message(self, app_name):
        self.clear_screen()
        self.stdout.write(
            self.format_header(f"Bootstrap 5 Migration of '{app_name}' is already complete!"),
            style_func=get_style_func(Color.GREEN)
        )
        self.stdout.write(f"It appears that '{app_name}' has already been fully migrated to Bootstrap 5!\n\n")
        self.stdout.write("If you feel this is in error, "
                          "please consult the table referenced in the migration guide\n"
                          "and `bootstrap3_to_5_completed.json`.\n\n")

    def _get_files_for_migration(self, files, file_name, do_re_check):
        if file_name is not None:
            files = [t for t in files if file_name in str(t)]

        # filter out already split bootstrap3 templates
        files = [t for t in files if '/bootstrap3/' not in str(t)]

        if do_re_check:
            self.clear_screen()
            self.write_response("\n\nRe-checking split Bootstrap 5 templates only.\n\n")
            files = [t for t in files if '/bootstrap5/' in str(t)]
        else:
            files = [t for t in files if '/bootstrap5/' not in str(t)]
        return files

    def get_templates_for_migration(self, app_name, template_name, do_re_check):
        app_templates = get_all_template_paths_for_app(app_name)
        available_templates = self._get_files_for_migration(app_templates, template_name, do_re_check)
        completed_templates = get_completed_templates_for_app(app_name)
        return set(available_templates).difference(completed_templates)

    def get_js_files_for_migration(self, app_name, js_name, do_re_check):
        app_js_files = get_all_javascript_paths_for_app(app_name)
        available_js_files = self._get_files_for_migration(app_js_files, js_name, do_re_check)
        completed_js_files = get_completed_javascript_for_app(app_name)
        return set(available_js_files).difference(completed_js_files)

    def migrate_files(self, files, app_name, spec, is_template):
        for file_path in files:
            short_path = get_short_path(app_name, file_path, is_template)
            self.clear_screen()
            file_type = "templates" if is_template else "javascript"
            self.stdout.write(self.format_header(f"Migrating {app_name} {file_type}..."))
            confirm = self.get_confirmation(f'Ready to migrate "{short_path}"?')
            if not confirm:
                self.write_response(f"ok, skipping {short_path}")
                continue

            self.stdout.write("\n")
            review_changes = self.get_confirmation('Do you want to review each change line-by-line here?')
            self.migrate_single_file(app_name, file_path, spec, is_template, review_changes)

    def migrate_single_file(self, app_name, file_path, spec, is_template, review_changes):
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
                    line_number, old_line, new_line, renames, flags, review_changes
                )

                new_lines.append(saved_line)
                if saved_line != old_line or flags:
                    has_changes = True
                if line_changelog:
                    file_changelog.extend(line_changelog)

            short_path = get_short_path(app_name, file_path, is_template)
            if has_changes:
                self.clear_screen()
                self.stdout.write(
                    self.format_header(f"Finalizing changes for {short_path}..."),
                    style_func=get_style_func(Color.YELLOW)
                )
                self.record_file_changes(file_path, app_name, file_changelog, is_template)
                if '/bootstrap5/' in str(file_path):
                    self.save_re_checked_file_changes(app_name, file_path, new_lines, is_template)
                else:
                    self.split_files_and_refactor(
                        app_name, file_path, old_lines, new_lines, is_template
                    )
            else:
                self.write_response(f"\nNo changes were needed for {short_path}. Skipping...\n\n")

    def confirm_and_get_line_changes(self, line_number, old_line, new_line, renames, flags, review_changes):
        changelog = []
        if renames or flags:
            changelog.append(self.format_header(f"Line {line_number}"))
            self.clear_screen()
            self.stdout.write(changelog[-1])
            for flag in flags:
                changelog.append("\nFlagged Code:")
                changelog.append(self.format_code(old_line, break_length=len(old_line) + 5))
                changelog.append(self.format_guidance(flag))
                if review_changes:
                    self.display_flag_summary(changelog)
                    self.enter_to_continue()
                    self.clear_screen()
                    self.stdout.write(self.format_header(
                        f"Additional changes to line {line_number} will be made..."
                    ))
                changelog.append("\n\n")
            if renames:
                changelog.append("\nDiff of changes:")
                changelog.extend(self.format_code(
                    f"-{old_line}+{new_line}",
                    split_lines=True,
                    break_length=max(len(old_line), len(new_line)) + 5
                ))
                changelog.append("Summary:\n  - " + "\n  - ".join(renames))
                self.display_rename_summary(changelog)
                changelog.append("\n\n")
                if review_changes:
                    confirm = self.get_confirmation("Keep changes?")
                    if not confirm:
                        changelog.append("CHANGES DISCARDED\n\n")
                        self.write_response("ok, discarding changes...")
                        return old_line, changelog
        return new_line, changelog

    def display_flag_summary(self, changelog):
        self.stdout.write(changelog[-3])
        self.stdout.write(changelog[-2], style_func=get_style_func(Color.YELLOW))
        self.stdout.write(changelog[-1])
        self.stdout.write("\nThis change requires manual intervention and is not made automatically. "
                          "\nThis guidance will be saved to migration logs for reference later. \n\n")

    def display_rename_summary(self, changelog):
        self.stdout.write("".join(changelog[-5:-3]))
        changes = changelog[-3].split('\n')
        self.stdout.write(changes[0], style_func=get_style_func(Color.RED))
        self.stdout.write(changes[1], style_func=get_style_func(Color.GREEN))
        self.stdout.write("".join(changelog[-2:]))
        changelog.append("\n\n")
        self.stdout.write("\n\n\nAnswering 'y' below will automatically make this change "
                          "in the Bootstrap 5 version of this file.\n\n")

    def record_file_changes(self, template_path, app_name, changelog, is_template):
        short_path = get_short_path(app_name, template_path.parent, is_template)
        readme_directory = Path(settings.BOOTSTRAP_MIGRATION_LOGS_DIR) / short_path
        readme_directory.mkdir(parents=True, exist_ok=True)
        extension = '.html' if is_template else '.js'
        readme_filename = template_path.name.replace(extension, '.md')
        readme_path = readme_directory / readme_filename
        with open(readme_path, 'w') as readme_file:
            readme_file.writelines(changelog)
        self.show_information_about_readme(readme_path)

    def show_information_about_readme(self, readme_path):
        self.stdout.write("\nThe changelog for all changes to the Bootstrap 5 "
                          "version of this file can be found here:\n")
        self.stdout.write(f"\n{readme_path}\n\n")
        self.stdout.write("** Please make a note of this for reviewing later.\n\n\n")

    def save_re_checked_file_changes(self, app_name, file_path, changed_lines, is_template):
        short_path = get_short_path(app_name, file_path, is_template)

        confirm = self.get_confirmation(f"\nSave changes to {short_path}?")

        if not confirm:
            self.write_response("ok, skipping save...")
            return

        with open(file_path, 'w') as readme_file:
            readme_file.writelines(changed_lines)
        self.stdout.write("\nChanges saved.")
        self.suggest_commit_message(f"re-ran migration for {short_path}")

    def split_files_and_refactor(self, app_name, file_path, bootstrap3_lines, bootstrap5_lines, is_template):
        short_path = get_short_path(app_name, file_path, is_template)

        confirm = self.get_confirmation(f'\nSplit {short_path} into Bootstrap 3 and Bootstrap 5 versions '
                                        f'and update references?')
        if not confirm:
            self.write_response("ok, canceling split and rolling back changes...")
            return

        bootstrap3_path, bootstrap5_path = self.get_split_file_paths(file_path)
        bootstrap3_short_path = get_short_path(app_name, bootstrap3_path, is_template)
        bootstrap5_short_path = get_short_path(app_name, bootstrap5_path, is_template)
        self.stdout.write(f"\n\nSplitting files:\n"
                          f"\n\t{bootstrap3_short_path}"
                          f"\n\t{bootstrap5_short_path}\n\n")
        if '/bootstrap5/' not in str(file_path):
            self.save_split_templates(
                file_path, bootstrap3_path, bootstrap3_lines, bootstrap5_path, bootstrap5_lines
            )
            self.stdout.write("\nUpdating references...")
            references = self.update_and_get_references(short_path, bootstrap3_short_path, is_template)
            if not is_template:
                # also check extension-less references for javascript files
                references.extend(self.update_and_get_references(
                    short_path.replace('.js', ''),
                    bootstrap3_short_path.replace('.js', ''),
                    is_template=False
                ))
            if references:
                self.stdout.write(f"\n\nUpdated references to {short_path} in these files:\n")
                self.stdout.write("\n".join(references))
            else:
                self.stdout.write(f"\n\nNo references were found for {short_path}...\n")
        self.suggest_commit_message(f"initial auto-migration for {short_path}, splitting templates")

    @staticmethod
    def save_split_templates(original_path, bootstrap3_path, bootstrap3_lines, bootstrap5_path, bootstrap5_lines):
        original_path.unlink(missing_ok=True)
        with open(bootstrap3_path, 'w') as file:
            file.writelines(bootstrap3_lines)
        with open(bootstrap5_path, 'w') as file:
            file.writelines(bootstrap5_lines)

    def _get_split_files(self, app_name):
        app_template_folder = get_app_template_folder(app_name)
        split_files = [f for f in app_template_folder.glob('**/*')
                       if f.is_file() and '/bootstrap3/' in str(f) and '/crispy/' not in str(f)]
        app_static_folder = get_app_static_folder(app_name)
        split_files.extend(
            f for f in app_static_folder.glob('**/*.js')
            if f.is_file() and '/bootstrap3/' in str(f)
        )
        return split_files

    def verify_split_references(self, app_name):
        self.clear_screen()
        self.stdout.write(self.format_header(f"Verifying references for {app_name}"))
        self.stdout.write(f"\n\nVerifying that references to split files "
                          f"in {app_name} have been updated...")
        split_files = self._get_split_files(app_name)
        template_path = get_app_template_folder(app_name)
        for file_path in split_files:
            is_template = file_path.is_relative_to(template_path)
            new_reference = get_short_path(app_name, file_path, is_template)
            old_reference = new_reference.replace("/bootstrap3/", "/")
            references = self.update_and_get_references(
                old_reference,
                new_reference,
                is_template
            )
            if not is_template:
                references.extend(self.update_and_get_references(
                    old_reference.replace(".js", ""),
                    new_reference.replace(".js", ""),
                    is_template=False
                ))
            if references:
                self.stdout.write(f"\n\nUpdated references to {old_reference} in these files:")
                self.stdout.write("\n".join(references))
                self.suggest_commit_message(f"updated path references to '{references}'")
        self.stdout.write("\n\nDone.\n\n")

    @staticmethod
    def update_and_get_references(old_reference, new_reference, is_template):
        references = []
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
                if file_contains_reference_to_path(filedata, old_reference):
                    references.append(str(file_path))
                    with open(file_path, 'w') as file:
                        file.write(replace_path_references(
                            filedata,
                            old_reference,
                            bootstrap5_reference if use_bootstrap5_reference else new_reference
                        ))
        return references

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
        flags = flag_changed_javascript_plugins(javascript_line, spec)
        reference_flags = flag_path_references_to_split_javascript_files(javascript_line, "bootstrap3")
        flags.extend(reference_flags)
        return flags

    @staticmethod
    def get_split_file_paths(file_path):
        bootstrap3_folder = file_path.parent / BOOTSTRAP_3
        bootstrap5_folder = file_path.parent / BOOTSTRAP_5
        bootstrap3_folder.mkdir(parents=True, exist_ok=True)
        bootstrap5_folder.mkdir(parents=True, exist_ok=True)
        return bootstrap3_folder / file_path.name, bootstrap5_folder / file_path.name

    @staticmethod
    def select_option_from_prompt(prompt, options):
        formatted_options = '/'.join(options)
        prompt_with_options = f"{prompt} [{formatted_options}] "
        while True:
            option = input(prompt_with_options).lower()
            if option in options:
                break
            else:
                prompt_with_options = f'Sorry, "{option}" is not an option. ' \
                                      f'Please choose from [{formatted_options}]: '
        return option

    def get_confirmation(self, prompt):
        option = self.select_option_from_prompt(prompt, ['y', 'n'])
        return option == 'y'

    def clear_screen(self):
        self.stdout.write("\033c")  # clear terminal screen

    @staticmethod
    def format_code(code_text, split_lines=False, break_length=80):
        lines = [
            '\n```\n',
            code_text,
            '\n```\n\n',
        ]
        if split_lines:
            return lines
        return "".join(lines)

    @staticmethod
    def format_header(header_text, break_length=80):
        break_line = get_break_line("*", break_length)
        return f'\n{break_line}\n\n{header_text}\n\n{break_line}\n\n'

    @staticmethod
    def format_guidance(guidance_text, break_length=80):
        break_line = get_break_line("- ", break_length)
        return f'Guidance:\n{break_line}\n{guidance_text}\n{break_line}\n\n'

    def write_response(self, response_text):
        self.stdout.write(f'\n{response_text}')
        time.sleep(2)

    @staticmethod
    def enter_to_continue():
        input("\nENTER to continue...")

    def suggest_commit_message(self, message):
        self.stdout.write("\nNow would be a good time to review changes with git and "
                          "commit before moving on to the next template.")
        self.stdout.write("\nSuggested command:")
        self.stdout.write(f"git commit --no-verify -m \"Bootstrap 5 Migration - {message}\"")
        self.stdout.write("\n")
        self.enter_to_continue()
