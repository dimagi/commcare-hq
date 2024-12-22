import time

from django.core.management import BaseCommand

from corehq.apps.hqwebapp.utils.bootstrap import BOOTSTRAP_3, BOOTSTRAP_5
from corehq.apps.hqwebapp.utils.bootstrap.changes import (
    get_spec,
    make_direct_css_renames,
    make_numbered_css_renames,
    make_select_form_control_renames,
    make_template_tag_renames,
    make_data_attribute_renames,
    make_javascript_dependency_renames,
    make_template_dependency_renames,
    flag_changed_css_classes,
    flag_stateful_button_changes_bootstrap5,
    flag_changed_javascript_plugins,
    flag_crispy_forms_in_template,
    flag_file_inputs,
    flag_inline_styles,
    flag_selects_without_form_control,
    add_todo_comments_for_flags,
    update_gruntfile,
)
from corehq.apps.hqwebapp.utils.bootstrap.git import (
    has_pending_git_changes,
    get_commit_string,
    apply_commit,
    ensure_no_pending_changes_before_continuing,
)
from corehq.apps.hqwebapp.utils.bootstrap.paths import (
    get_app_template_folder,
    get_app_static_folder,
    get_short_path,
    get_all_template_paths_for_app,
    get_all_javascript_paths_for_app,
    is_split_path,
    is_bootstrap5_path,
    is_ignored_path,
    GRUNTFILE_PATH,
)
from corehq.apps.hqwebapp.utils.bootstrap.references import (
    update_and_get_references,
    get_requirejs_reference,
)
from corehq.apps.hqwebapp.utils.bootstrap.status import (
    get_completed_templates_for_app,
    get_completed_javascript_for_app,
    is_app_completed,
    is_app_in_progress,
    mark_app_as_in_progress,
)
from corehq.apps.hqwebapp.utils.management_commands import (
    get_break_line,
    get_confirmation,
    enter_to_continue,
)


class Command(BaseCommand):
    help = "This command helps migrate CCHQ applications from Bootstrap 3 to Bootstrap 5."
    skip_all = False
    no_split = False

    def add_arguments(self, parser):
        parser.add_argument('app_name')
        parser.add_argument(
            '--filename',
            help="Specify the exact filename you would like to split and migrate.",
        )
        parser.add_argument(
            '--no-split',
            action='store_true',
            default=False,
            help="Do not split files, make migration changes directly to files."
        )
        parser.add_argument(
            '--skip-all',
            action='store_true',
            default=False,
            help="Skip all confirmation when migrating."
        )
        parser.add_argument(
            '--verify-references',
            action='store_true',
            default=False,
            help="Verify that all references to split files have been updated"
        )

    def handle(self, app_name, **options):
        selected_filename = options.get('filename')

        is_app_migration_complete = is_app_completed(app_name)

        if is_app_migration_complete and not selected_filename:
            self.show_completed_message(app_name)
            return

        if is_app_migration_complete and selected_filename:
            self.stdout.write(self.style.WARNING(
                f"\nIt appears the app '{app_name}' is already marked as complete.\n"
            ))
            confirm = get_confirmation(
                f"Continue migrating '{selected_filename}'?", default='y'
            )
            if not confirm:
                return

        self.no_split = options.get('no_split')
        if not is_app_in_progress(app_name) and not is_app_migration_complete and not self.no_split:
            self.stdout.write(self.style.WARNING(
                f"\n\n'{app_name}' is not marked as 'in progress'.\n"
            ))
            confirm = get_confirmation(
                f"Would you like to mark {app_name} as 'in progress' before continuing?",
                default='y'
            )
            if confirm:
                has_changes = has_pending_git_changes()
                mark_app_as_in_progress(app_name)
                self.suggest_commit_message(
                    f"marking {app_name} as in progress",
                    show_apply_commit=not has_changes
                )

        self.skip_all = options.get('skip_all')
        if self.skip_all and self.no_split:
            self.stderr.write(
                "\n--skip-all and --no-split cannot be used at the same time.\n"
            )
            return

        if self.skip_all and has_pending_git_changes():
            self.stdout.write(self.style.ERROR(
                "You have un-committed changes. Please commit these changes before proceeding...\n"
            ))
            ensure_no_pending_changes_before_continuing()

        spec = get_spec('bootstrap_3_to_5')
        verify_references = options.get('verify_references')

        if verify_references:
            self.verify_split_references(app_name)
            return

        app_templates = self.get_templates_for_migration(app_name, selected_filename)
        migrated_templates = self.migrate_files(app_templates, app_name, spec, is_template=True)

        app_javascript = self.get_js_files_for_migration(app_name, selected_filename)
        self.migrate_files(app_javascript, app_name, spec, is_template=False)

        mocha_paths = [path for path in migrated_templates
                       if f'{app_name}/spec/' in str(path)]
        if mocha_paths:
            mocha_paths = [get_short_path(app_name, path, True)
                           for path in mocha_paths]
            self.make_updates_to_gruntfile(app_name, mocha_paths)

        self.show_next_steps(app_name)

    def make_updates_to_gruntfile(self, app_name, mocha_paths):
        has_changes = has_pending_git_changes()
        self.clear_screen()
        self.stdout.write(self.style.WARNING(
            self.format_header("Mocha (javascript test) files were split!")
        ))
        self.stdout.write(self.style.MIGRATE_LABEL(
            "Updating Gruntfile.js...\n\n"
        ))
        with open(GRUNTFILE_PATH, 'r+') as file:
            filedata = file.read()
            file.seek(0)
            file.write(update_gruntfile(
                filedata, mocha_paths
            ))
        self.suggest_commit_message(
            f"Updated 'Gruntfile.js' after splitting '{app_name}'.",
            show_apply_commit=not has_changes
        )

    def show_next_steps(self, app_name):
        self.clear_screen()
        self.stdout.write(self.style.SUCCESS(
            self.format_header(f"All done with Step 2 of migrating {app_name}!")
        ))
        self.stdout.write(self.style.WARNING(
            "IMPORTANT: If this is the first time running this command, "
            "it's recommended to re-run the command\nat least one more "
            "time in the event of nested dependencies / inheritance "
            "in split files.\n\n"
        ))
        if not self.no_split:
            self.stdout.write("After this, please update `bootstrap5_diff_config.json` "
                              "using the command below and follow the next steps after.\n\n")
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"./manage.py build_bootstrap5_diffs --update_app {app_name}\n\n"
            ))
        self.stdout.write("Thank you for your dedication to this migration! <3\n\n")
        self.stdout.write("You may review the full migration guide here:")
        self.stdout.write(self.style.MIGRATE_HEADING(
            "commcarehq.org/styleguide/b5/migration/\n\n\n"
        ))

    def show_completed_message(self, app_name):
        self.clear_screen()
        self.stdout.write(self.style.SUCCESS(
            self.format_header(f"Bootstrap 5 Migration of '{app_name}' is already complete!")
        ))
        self.stdout.write(f"It appears that '{app_name}' has already been fully migrated to Bootstrap 5!\n\n")
        self.stdout.write("If you feel this is in error, "
                          "please consult the table referenced in the migration guide\n"
                          "and `bootstrap3_to_5_completed.json`.\n\n")

    @staticmethod
    def _get_files_for_migration(app_name, files, file_name):
        if file_name:
            files = [path for path in files if file_name in str(path)]
            if len(files) > 1 and not is_bootstrap5_path(file_name):
                files = [
                    path for path in files if not is_bootstrap5_path(path)
                ]
            return files
        return [path for path in files
                if not (is_split_path(path) or is_ignored_path(app_name, path))]

    def get_templates_for_migration(self, app_name, selected_filename):
        app_templates = get_all_template_paths_for_app(app_name)
        available_templates = self._get_files_for_migration(
            app_name, app_templates, selected_filename
        )
        if selected_filename:
            return available_templates
        completed_templates = get_completed_templates_for_app(app_name)
        return set(available_templates).difference(completed_templates)

    def get_js_files_for_migration(self, app_name, selected_filename):
        app_js_files = get_all_javascript_paths_for_app(app_name)
        available_js_files = self._get_files_for_migration(
            app_name, app_js_files, selected_filename
        )
        if selected_filename:
            return available_js_files
        completed_js_files = get_completed_javascript_for_app(app_name)
        return set(available_js_files).difference(completed_js_files)

    def migrate_files(self, files, app_name, spec, is_template):
        """
        Migrates a list of files if there are changes.

        :param app_name: string (app name that's being migrated)
        :param files: list(Path) (object)
        :param spec: dict
        :param is_template: boolean (whether the file is a template or javascript file)
        :return: list(Path) (list of all Paths that had changes)
        """
        migrated_files = []
        for index, file_path in enumerate(files):
            short_path = get_short_path(app_name, file_path, is_template)
            self.clear_screen()
            file_type = "templates" if is_template else "javascript"
            self.stdout.write(self.format_header(f"Migrating {app_name} {file_type}..."))

            if not self.skip_all:
                confirm = get_confirmation(f'Ready to migrate "{short_path}" ({index + 1} of {len(files)})?',
                                           default='y')
                if not confirm:
                    self.write_response(f"ok, skipping {short_path}")
                    continue

            self.stdout.write("\n")
            if not self.skip_all:
                review_changes = get_confirmation(
                    'Do you want to review each change line-by-line here?', default='y'
                )
            else:
                review_changes = False
            if self.migrate_single_file(app_name, file_path, spec, is_template, review_changes):
                migrated_files.append(file_path)
        return migrated_files

    def migrate_single_file(self, app_name, file_path, spec, is_template, review_changes):
        """
        This runs through each line in a file and obtains flagged todos and changes for each line
        and applies them, depending on user input (if skip-all isn't active).

        :param app_name: string (app name that's being migrated)
        :param file_path: Path (object)
        :param spec: dict
        :param is_template: boolean (whether the file is a template or javascript file)
        :param review_changes: boolean (option of whether the user should review line-by-line)
        :return: boolean (True if changes were made, False if no changes)
        """
        is_fresh_migration = not is_bootstrap5_path(file_path)
        with open(file_path, 'r') as current_file:
            old_lines = current_file.readlines()
            new_lines = []
            has_changes = False
            file_changelog = []

            for line_number, old_line in enumerate(old_lines):
                if is_template:
                    new_line, renames = self.make_template_line_changes(old_line, spec, is_fresh_migration)
                    flags = self.get_flags_in_template_line(old_line, spec)
                else:
                    new_line, renames = self.make_javascript_line_changes(old_line, spec)
                    flags = self.get_flags_in_javascript_line(old_line, spec)

                saved_line, line_changelog = self.confirm_and_get_line_changes(
                    line_number, old_line, new_line, renames, flags, review_changes
                )
                saved_line = add_todo_comments_for_flags(flags, saved_line, is_template)

                new_lines.append(saved_line)
                if saved_line != old_line or flags:
                    has_changes = True
                if line_changelog:
                    file_changelog.extend(line_changelog)

            short_path = get_short_path(app_name, file_path, is_template)
            if has_changes:
                self.clear_screen()
                self.stdout.write(self.style.WARNING(
                    self.format_header(f"Finalizing changes for {short_path}...")
                ))
                if self.no_split:
                    self.migrate_file_in_place(app_name, file_path, new_lines, is_template)
                    if is_template:
                        self.show_next_steps_after_migrating_file_in_place(short_path)
                elif is_split_path(file_path):
                    self.migrate_file_again(app_name, file_path, new_lines, is_template)
                else:
                    self.split_files_and_refactor(
                        app_name, file_path, old_lines, new_lines, is_template
                    )
                return True
            else:
                self.write_response(f"\nNo changes were needed for {short_path}. Skipping...\n\n")
        return False

    def confirm_and_get_line_changes(self, line_number, old_line, new_line, renames, flags, review_changes):
        changelog = []
        if renames or flags:
            changelog.append(self.format_header(f"Line {line_number}"))
            self.clear_screen()
            self.stdout.write(changelog[-1])
            for flag in flags:
                guidance = flag[1]
                changelog.append("\nFlagged Code:")
                changelog.append(self.format_code(old_line, break_length=len(old_line) + 5))
                changelog.append(self.format_guidance(guidance))
                if review_changes:
                    self.display_flag_summary(changelog)
                    enter_to_continue()
                    self.clear_screen()
                    self.stdout.write(self.format_header(
                        f"Additional changes to line {line_number} will be made..."
                    ))
                changelog.append("\n\n")
            if renames:
                changelog.append("\nDiff of changes:")
                if not old_line.endswith('\n'):
                    # in case there isn't a new line at the end, add one to avoid errors
                    # this will also fix linting in the new_line :)
                    old_line = f'{old_line}\n'
                    new_line = f'{new_line}\n'
                changelog.extend(self.format_code(
                    f"-{old_line}+{new_line}",
                    split_lines=True,
                    break_length=max(len(old_line), len(new_line)) + 5
                ))
                changelog.append("Summary:\n  - " + "\n  - ".join(renames))
                self.display_rename_summary(changelog)
                changelog.append("\n\n")
                if review_changes:
                    confirm = get_confirmation("Keep changes?", default='y')
                    if not confirm:
                        changelog.append("CHANGES DISCARDED\n\n")
                        self.write_response("ok, discarding changes...")
                        return old_line, changelog
        return new_line, changelog

    def display_flag_summary(self, changelog):
        self.stdout.write(changelog[-3])
        self.stdout.write(self.style.WARNING(changelog[-2]))
        self.stdout.write(changelog[-1])
        self.stdout.write("\nThis change requires manual intervention and is not made automatically. "
                          "\nThis guidance will be saved to migration logs for reference later. \n\n")

    def display_rename_summary(self, changelog):
        self.stdout.write("".join(changelog[-5:-3]))
        changes = changelog[-3].split('\n')
        self.stdout.write(self.style.ERROR(changes[0]))
        self.stdout.write(self.style.SUCCESS(changes[1]))
        self.stdout.write("".join(changelog[-2:]))
        changelog.append("\n\n")
        self.stdout.write("\n\n\nAnswering 'y' below will automatically make this change "
                          "in the Bootstrap 5 version of this file.\n\n")

    def migrate_file_in_place(self, app_name, file_path, bootstrap5_lines, is_template):
        short_path = get_short_path(app_name, file_path, is_template)
        confirm = get_confirmation(f"Apply changes to '{short_path}'?", default='y')
        if not confirm:
            self.write_response("ok, discarding changes...")

        has_changes = has_pending_git_changes()
        if has_changes:
            self.prompt_user_to_commit_changes()
            has_changes = has_pending_git_changes()

        with open(file_path, 'w') as file:
            file.writelines(bootstrap5_lines)
        self.suggest_commit_message(
            f"initial auto-migration for {short_path}, migrated in-place",
            show_apply_commit=not has_changes
        )

    def show_next_steps_after_migrating_file_in_place(self, short_path):
        self.stdout.write(self.style.MIGRATE_LABEL(
            "\n\nPlease take a moment now to search for all views referencing\n"
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"{short_path}\n"
        ))
        self.stdout.write(self.style.MIGRATE_LABEL(
            "and make sure that these views have the @use_bootstrap5 decorator applied.\n"
            "Afterwards, please commit these changes and proceed to the next file. Thank you!\n\n"
        ))
        self.stdout.write(
            "See: https://www.commcarehq.org/styleguide/b5/migration/#migrating-views"
        )
        enter_to_continue()
        if has_pending_git_changes():
            self.stdout.write(self.style.WARNING(
                "\n\nDon't forget to commit these changes!"
            ))
            self.suggest_commit_message(
                f"added use_bootstrap5 decorator to views referencing {short_path}"
            )

    def migrate_file_again(self, app_name, file_path, bootstrap5_lines, is_template):
        bootstrap5_path = (file_path if is_bootstrap5_path(file_path)
                           else self.get_bootstrap5_path(file_path))

        migrated_file_short_path = get_short_path(app_name, file_path, is_template)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"NOTE: This is a re-migration of {migrated_file_short_path}."
        ))

        bootstrap5_short_path = get_short_path(app_name, bootstrap5_path, is_template)
        confirm = get_confirmation(
            f"\nApply migration changes to {bootstrap5_short_path}?", default='y'
        )
        if not confirm:
            self.write_response("ok, skipping save...")
            return

        has_changes = has_pending_git_changes()
        if has_changes:
            self.prompt_user_to_commit_changes()
            has_changes = has_pending_git_changes()

        with open(bootstrap5_path, 'w') as bootstrap5_file:
            bootstrap5_file.writelines(bootstrap5_lines)

        if has_pending_git_changes():
            self.stdout.write(
                f"\nChanges applied to {bootstrap5_short_path}."
            )
            self.suggest_commit_message(
                f"re-ran migration for {migrated_file_short_path}",
                show_apply_commit=not has_changes
            )
        else:
            self.stdout.write("\nNo changes were necessary!\n")
            enter_to_continue()

    def split_files_and_refactor(self, app_name, file_path, bootstrap3_lines, bootstrap5_lines, is_template):
        short_path = get_short_path(app_name, file_path, is_template)

        if not self.skip_all:
            confirm = get_confirmation(f'\nSplit {short_path} into Bootstrap 3 and Bootstrap 5 versions '
                                       f'and update references?', default='y')
            if not confirm:
                self.write_response("ok, canceling split and rolling back changes...")
                return

        has_changes = has_pending_git_changes()
        if has_changes:
            self.prompt_user_to_commit_changes()
            has_changes = has_pending_git_changes()

        bootstrap3_path, bootstrap5_path = self.get_split_file_paths(file_path)
        bootstrap3_short_path = get_short_path(app_name, bootstrap3_path, is_template)
        bootstrap5_short_path = get_short_path(app_name, bootstrap5_path, is_template)
        self.stdout.write(f"\n\nSplitting files:\n"
                          f"\n\t{bootstrap3_short_path}"
                          f"\n\t{bootstrap5_short_path}\n\n")
        self.save_split_templates(
            file_path, bootstrap3_path, bootstrap3_lines, bootstrap5_path, bootstrap5_lines
        )
        self.stdout.write("\nUpdating references...")
        references = update_and_get_references(short_path, bootstrap3_short_path, is_template)
        if not is_template:
            # also check extension-less references for javascript files
            references.extend(update_and_get_references(
                get_requirejs_reference(short_path),
                get_requirejs_reference(bootstrap3_short_path),
                is_template=False
            ))
        if references:
            self.stdout.write(f"\n\nUpdated references to {short_path} in these files:\n")
            self.stdout.write("\n".join(references))
        else:
            self.stdout.write(f"\n\nNo references were found for {short_path}...\n")
        self.suggest_commit_message(
            f"initial auto-migration for {short_path}, splitting templates",
            show_apply_commit=not has_changes
        )

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
            references = update_and_get_references(
                old_reference,
                new_reference,
                is_template
            )
            if not is_template:
                references.extend(update_and_get_references(
                    get_requirejs_reference(old_reference),
                    get_requirejs_reference(new_reference),
                    is_template=False
                ))
            if references:
                self.stdout.write(self.style.MIGRATE_HEADING(
                    f"\n\nUpdated references to {old_reference} in these files:"
                ))
                self.stdout.write("\n".join(references))
                self.suggest_commit_message(f"updated path references to '{references}'")
        self.stdout.write("\n\nDone.\n\n")

    @staticmethod
    def make_template_line_changes(old_line, spec, is_fresh_migration):
        new_line, renames = make_direct_css_renames(old_line, spec)

        if is_fresh_migration:
            # These changes can only be done on a fresh migration (only bootstrap3 templates)
            # as changes like col-md-1 > col-lg-1 can only be applied one time, as the classes
            # being replaced are not deprecated in the bootstrap 3 templates. Only the column size
            # definitions have changes.
            new_line, numbered_renames = make_numbered_css_renames(new_line, spec)
            renames.extend(numbered_renames)

        new_line, attribute_renames = make_data_attribute_renames(new_line, spec)
        renames.extend(attribute_renames)
        new_line, select_renames = make_select_form_control_renames(new_line, spec)
        renames.extend(select_renames)
        new_line, template_dependency_renames = make_template_dependency_renames(new_line, spec)
        renames.extend(template_dependency_renames)
        new_line, template_tag_renames = make_template_tag_renames(new_line, spec)
        renames.extend(template_tag_renames)
        return new_line, renames

    @staticmethod
    def get_flags_in_template_line(template_line, spec):
        flags = flag_changed_css_classes(template_line, spec)
        flags.extend(flag_stateful_button_changes_bootstrap5(template_line))
        flags.extend(flag_crispy_forms_in_template(template_line))
        flags.extend(flag_file_inputs(template_line))
        flags.extend(flag_inline_styles(template_line))
        flags.extend(flag_selects_without_form_control(template_line))
        return flags

    @staticmethod
    def make_javascript_line_changes(old_line, spec):
        new_line, renames = make_javascript_dependency_renames(old_line, spec)
        return new_line, renames

    @staticmethod
    def get_flags_in_javascript_line(javascript_line, spec):
        flags = flag_changed_javascript_plugins(javascript_line, spec)
        return flags

    @staticmethod
    def get_bootstrap5_path(bootstrap3_path):
        bootstrap5_folder = bootstrap3_path.parent.parent / BOOTSTRAP_5
        bootstrap5_folder.mkdir(parents=True, exist_ok=True)
        return bootstrap5_folder / bootstrap3_path.name

    @staticmethod
    def get_split_file_paths(file_path):
        bootstrap3_folder = file_path.parent / BOOTSTRAP_3
        bootstrap5_folder = file_path.parent / BOOTSTRAP_5
        bootstrap3_folder.mkdir(parents=True, exist_ok=True)
        bootstrap5_folder.mkdir(parents=True, exist_ok=True)
        return bootstrap3_folder / file_path.name, bootstrap5_folder / file_path.name

    def clear_screen(self):
        self.stdout.write("\033[2J\033[H")  # clear terminal screen

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

    def prompt_user_to_commit_changes(self):
        self.stdout.write(self.style.ERROR(
            "\nYou have un-committed changes! Please commit these changes before proceeding. Thank you!"
        ))

    def suggest_commit_message(self, message, show_apply_commit=False):
        if self.skip_all and show_apply_commit:
            apply_commit(message)
            return

        self.stdout.write("\nNow would be a good time to review changes with git and "
                          "commit before moving on to the next template.")
        if show_apply_commit:
            confirm = get_confirmation("\nAutomatically commit these changes?", default='y')
            if confirm:
                apply_commit(message)
                return
        commit_string = get_commit_string(message)
        self.stdout.write("\n\nSuggested command:\n")
        self.stdout.write(self.style.MIGRATE_HEADING(commit_string))
        self.stdout.write("\n")
        enter_to_continue()
