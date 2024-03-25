from django.core.management import BaseCommand

from corehq.apps.hqwebapp.utils.bootstrap.paths import (
    get_all_template_paths_for_app,
    get_all_javascript_paths_for_app,
    get_split_paths,
    get_short_path,
)
from corehq.apps.hqwebapp.utils.management_commands import (
    get_confirmation,
    get_style_func,
    Color,
)
from corehq.apps.hqwebapp.utils.bootstrap.references import (
    get_references,
    update_and_get_references,
    get_requirejs_reference,
)
from corehq.apps.hqwebapp.utils.bootstrap.status import (
    mark_app_as_complete,
    mark_template_as_complete,
    mark_javascript_as_complete,
)


class Command(BaseCommand):
    help = "This command helps finalize the migration of CCHQ applications from Bootstrap 3 to Bootstrap 5."

    def add_arguments(self, parser):
        parser.add_argument('app_name')
        parser.add_argument(
            '--template',
            help="Specify the exact template name you would like to un-split and mark as complete",
        )
        parser.add_argument(
            '--javascript',
            help="Specify the exact template name you would like to un-split and mark as complete",
        )

    def handle(self, app_name, **options):
        template = options.get('template')
        if template:
            self.mark_file_as_complete(app_name, template, is_template=True)
            return
        javascript = options.get('javascript')
        if javascript:
            self.mark_file_as_complete(app_name, javascript, is_template=False)
            return
        self.mark_app_as_complete(app_name)

    def mark_app_as_complete(self, app_name):
        split_paths = [get_short_path(app_name, path, True)
                       for path in get_split_paths(get_all_template_paths_for_app(app_name))]
        split_paths.extend([get_short_path(app_name, path, False)
                            for path in get_split_paths(get_all_javascript_paths_for_app(app_name))])
        if len(split_paths) > 0:
            self.stdout.write(
                f"\nCannot mark '{app_name}' as complete as there are "
                f"{len(split_paths)} file(s) left to migrate.\n",
                style_func=get_style_func(Color.RED)
            )
            self.optional_display_list("Show remaining files?", split_paths)
            return
        self.stdout.write(
            f"\nMarking '{app_name}' as complete!\n\n",
            style_func=get_style_func(Color.GREEN)
        )
        mark_app_as_complete(app_name)

    def mark_file_as_complete(self, app_name, filename, is_template):
        file_type = "template" if is_template else "js file"
        if is_template:
            relevant_paths = get_all_template_paths_for_app(app_name)
        else:
            relevant_paths = get_all_javascript_paths_for_app(app_name)
        bootstrap3_path, bootstrap5_path, destination_path = self.verify_filename_and_get_paths(
            app_name, filename, relevant_paths, is_template
        )
        if destination_path is None:
            self.stdout.write(
                f"\nIt appears that the {file_type} '{filename}'\n"
                f"could not be found in '{app_name}'.",
                style_func=get_style_func(Color.RED)
            )
            self.stdout.write("Please check that you have the right path and try again.\n\n")
            return

        if bootstrap5_path:
            split_status = self.un_split_files(app_name, bootstrap3_path, bootstrap5_path,
                                               destination_path, is_template=True)
            if not split_status:
                self.stdout.write("Cancelling operation.\n\n")
                return

        destination_short_path = get_short_path(app_name, destination_path, is_template)
        if is_template:
            mark_template_as_complete(app_name, destination_short_path)
        else:
            mark_javascript_as_complete(app_name, destination_short_path)
        self.suggest_commit_message(
            f"Marked {file_type} '{destination_short_path}' as complete and un-split files."
        )
        self.show_next_steps(app_name)

    def verify_filename_and_get_paths(self, app_name, filename, relevant_paths, is_template):
        filename = self.sanitize_bootstrap3_from_filename(filename)
        if filename is False:
            return False

        destination = filename.replace('bootstrap5/', '')
        bootstrap3_path = self.get_valid_path(app_name, destination, get_split_paths(relevant_paths, 'bootstrap3'),
                                              is_template, 'bootstrap3')
        if bootstrap3_path:
            destination = get_short_path(app_name, bootstrap3_path, is_template).replace('bootstrap3/', '')
        bootstrap5_path = self.get_valid_path(app_name, destination, get_split_paths(relevant_paths, 'bootstrap5'),
                                              is_template, 'bootstrap5')
        if bootstrap5_path:
            destination_path = bootstrap5_path.parent.parent / bootstrap5_path.name
        else:
            destination_path = self.get_valid_path(
                app_name, destination, relevant_paths, is_template
            )
        return bootstrap3_path, bootstrap5_path, destination_path

    def sanitize_bootstrap3_from_filename(self, filename):
        if 'bootstrap3/' in filename:
            self.stdout.write(
                f"You specified '{filename}', which appears to be a Bootstrap 3 path!\n"
                f"This file cannot be marked as complete with this tool.\n\n",
                style_func=get_style_func(Color.RED)
            )
            filename = filename.replace('bootstrap3/', 'bootstrap5/')
            confirm = get_confirmation(f"Did you mean, '{filename}?")
            if not confirm:
                self.stdout.write("Ok, aborting operation.\n\n")
                return False
        return filename

    def get_valid_path(self, app_name, destination_filename, relevant_paths, is_template, split_folder=None):
        split_folder_path = f'{split_folder}/' if split_folder is not None else ''
        matching_paths = [
            p for p in relevant_paths
            if str(p).replace(split_folder_path, '').endswith(destination_filename)
        ]
        if len(matching_paths) == 0:
            return None
        return self.select_path(app_name, matching_paths, is_template)

    def select_path(self, app_name, matching_paths, is_template):
        selected_path = matching_paths[0]
        if len(matching_paths) > 1:
            file_type = "templates" if is_template else "js files"
            self.stdout.write(f"\nFound {len(matching_paths)} "
                              f"{file_type} matching that name...\n")
            for path in matching_paths:
                short_path = get_short_path(app_name, path, is_template)
                confirm = get_confirmation(f"Select {short_path}?")
                if confirm:
                    selected_path = path
                    break
        return selected_path

    def un_split_files(self, app_name, bootstrap3_path, bootstrap5_path, destination_path, is_template):
        bootstrap5_short_path = get_short_path(app_name, bootstrap5_path, is_template)
        destination_short_path = get_short_path(app_name, destination_path, is_template)

        self.stdout.write(f"\n\nUn-split to '{destination_short_path}':")
        self.stdout.write(
            f"keep the contents of the bootstrap 5 version ({bootstrap5_short_path})",
            style_func=get_style_func(Color.GREEN)
        )
        if bootstrap3_path:
            bootstrap3_short_path = get_short_path(app_name, bootstrap3_path, is_template)
            self.stdout.write(
                f"discard the contents of the bootstrap 3 version ({bootstrap3_short_path})",
                style_func=get_style_func(Color.RED)
            )
        else:
            bootstrap3_short_path = bootstrap5_short_path.replace('/bootstrap5/', '/bootstrap3/')
        confirm = get_confirmation("Proceed?")
        if not confirm:
            return False
        if self.do_bootstrap3_references_exist(app_name, bootstrap3_short_path, is_template):
            return False
        self.apply_un_split_actions_to_files(bootstrap3_path, bootstrap5_path, destination_path)
        self.update_references_and_print_summary(
            app_name, bootstrap5_short_path, destination_short_path, is_template
        )
        return True

    @staticmethod
    def apply_un_split_actions_to_files(bootstrap3_path, bootstrap5_path, destination_path):
        if bootstrap3_path:
            # delete bootstrap3 version of file
            bootstrap3_path.unlink(missing_ok=True)
        # move bootstrap5 version of file to new destination
        bootstrap5_path.rename(destination_path)

    def do_bootstrap3_references_exist(self, app_name, bootstrap3_short_path, is_template):
        bootstrap3_references = get_references(bootstrap3_short_path)
        if not is_template:
            bootstrap3_references.extend(get_references(get_requirejs_reference(bootstrap3_short_path)))
        if len(bootstrap3_references) == 0:
            return False
        self.stdout.write(
            f"{len(bootstrap3_references)} reference(s) to the Bootstrap 3 version still exist!",
            style_func=get_style_func(Color.RED)
        )
        self.stdout.write("Please ensure these references are properly "
                          "migrated before marking this file as complete!\n")
        self.optional_display_list("List references?", [
            get_short_path(app_name, path, is_template) for path in bootstrap3_references
        ])
        return True

    def update_references_and_print_summary(self, app_name, bootstrap5_short_path,
                                            destination_short_path, is_template):
        references = update_and_get_references(bootstrap5_short_path, destination_short_path, is_template)
        if not is_template:
            references.extend(update_and_get_references(
                get_requirejs_reference(bootstrap5_short_path),
                get_requirejs_reference(destination_short_path),
                False
            ))
        self.stdout.write(
            f"Updated {len(references)} references to {bootstrap5_short_path}\n"
            f"with the new reference to {destination_short_path}!",
            style_func=get_style_func(Color.GREEN)
        )
        self.optional_display_list("List references?", [
            get_short_path(app_name, path, is_template) for path in references
        ])

    def optional_display_list(self, confirmation_message, list_to_display):
        confirm = get_confirmation(confirmation_message)
        if confirm:
            self.stdout.write("\n\n")
            self.stdout.write("\n".join(list_to_display))
            self.stdout.write("\n\n")

    def suggest_commit_message(self, message):
        self.stdout.write("\nNow would be a good time to review changes with git and commit.")
        self.stdout.write("\nSuggested command:")
        self.stdout.write(f"git commit --no-verify -m \"Bootstrap 5 Migration - {message}\"")
        self.stdout.write("\n")

    def show_next_steps(self, app_name):
        self.stdout.write("\nDone!\n\n", style_func=get_style_func(Color.GREEN))
        self.stdout.write("After reviewing and committing changes, please run:\n")
        self.stdout.write(f"./manage.py build_bootstrap5_diffs --update_app {app_name}\n\n")
        self.stdout.write("Commit those changes, if any.\n\n"
                          "Then run the full command and commit those changes:\n")
        self.stdout.write("./manage.py build_bootstrap5_diffs\n\n")
        self.stdout.write("Thank you! <3\n\n")
