import difflib
import json
import os
from pathlib import Path
import re
import shutil

from django.core.management import BaseCommand

from corehq.apps.hqwebapp.utils.bootstrap.git import (
    has_pending_git_changes,
    apply_commit,
    get_commit_string,
)
from corehq.apps.hqwebapp.utils.bootstrap.paths import (
    COREHQ_BASE_DIR,
    get_app_template_folder,
    get_app_static_folder,
    get_all_template_paths_for_app,
    get_split_folders,
    get_all_javascript_paths_for_app,
    TRACKED_JS_FOLDERS,
    get_app_name_and_slug,
)
from corehq.apps.hqwebapp.utils.management_commands import get_confirmation

DIFF_CONFIG_FILE = "apps/hqwebapp/tests/data/bootstrap5_diff_config.json"
DIFF_STORAGE_FOLDER = "apps/hqwebapp/tests/data/bootstrap5_diffs/"


def get_diff_filename(filename_bootstrap3, filename_bootstrap5, file_type):
    if filename_bootstrap3 == filename_bootstrap5:
        filename = filename_bootstrap5
    else:
        filename_bootstrap3 = get_renamed_filename(filename_bootstrap3)
        filename_bootstrap5 = get_renamed_filename(filename_bootstrap5)
        filename = f"{filename_bootstrap3}.{filename_bootstrap5}"
    if file_type == "stylesheet":
        filename = f"{filename}.style"
    return f"{filename}.diff.txt"


def get_renamed_filename(filename):
    return filename.replace('.scss', '').replace('.less', '').replace('/', '_')


def get_diff(file_v1, file_v2):
    with open(file_v1, "r") as fv1, open(file_v2, "r") as fv2:
        data_v1 = fv1.readlines()
        data_v2 = fv2.readlines()
        return list(difflib.unified_diff(data_v1, data_v2))


def get_bootstrap5_diff_config():
    config_file_path = COREHQ_BASE_DIR / DIFF_CONFIG_FILE
    with open(config_file_path, encoding='utf-8') as f:
        return json.loads(f.read())


def update_bootstrap5_diff_config(config):
    config_file_path = COREHQ_BASE_DIR / DIFF_CONFIG_FILE
    config_string = json.dumps(config, indent=2)
    with open(config_file_path, "w") as f:
        f.writelines(config_string + '\n')


def clear_diffs_folder():
    diff_storage = COREHQ_BASE_DIR / DIFF_STORAGE_FOLDER
    shutil.rmtree(diff_storage)


def get_bootstrap5_filepaths(full_diff_config):
    for parent_path, directory_diff_config in full_diff_config.items():
        for diff_config in directory_diff_config:
            directory_bootstrap3, directory_bootstrap5 = diff_config['directories']
            migrated_files = diff_config.get('files')
            compare_all_files = diff_config.get('compare_all_files', False)
            file_type = diff_config["file_type"]
            label = diff_config["label"]

            path_bootstrap3 = COREHQ_BASE_DIR / parent_path / directory_bootstrap3
            path_bootstrap5 = COREHQ_BASE_DIR / parent_path / directory_bootstrap5

            if compare_all_files:
                migrated_files = []
                for path in path_bootstrap3.glob('**/*'):
                    if path.is_file() and not path.name.startswith("."):
                        path = os.path.relpath(path, path_bootstrap3)
                        pair = [path, path]
                        if file_type == "stylesheet":
                            pair[1] = re.sub(r'\.less$', '.scss', pair[1])
                        migrated_files.append(pair)

            for filename_bootstrap3, filename_bootstrap5 in migrated_files:
                diff_filename = get_diff_filename(filename_bootstrap3, filename_bootstrap5, file_type)
                diff_filepath = COREHQ_BASE_DIR / DIFF_STORAGE_FOLDER / label / diff_filename
                diff_filepath.parent.mkdir(parents=True, exist_ok=True)
                bootstrap3_filepath = path_bootstrap3 / filename_bootstrap3
                bootstrap5_filepath = path_bootstrap5 / filename_bootstrap5

                yield bootstrap3_filepath, bootstrap5_filepath, diff_filepath


def get_relative_folder_paths(config_path, folders):
    relevant_folders = [path for path in folders if config_path in path]
    return sorted([path.replace(config_path, '').lstrip('/') for path in relevant_folders])


def get_folder_config(app_name, path, js_folder=None):
    """This only supports javascript and template files.
    Stylesheets should be handled separately.
    """
    _, app_name = get_app_name_and_slug(app_name)
    if js_folder:
        label = "javascript" / Path(app_name) / js_folder / path
    else:
        label = Path(app_name) / path
    return {
        "directories": [
            str(Path(path) / 'bootstrap3'),
            str(Path(path) / 'bootstrap5')
        ],
        "file_type": "javascript" if js_folder is not None else "template",
        "label": str(label),
        "compare_all_files": True
    }


def get_parent_path(app_name, js_folder=None):
    config_path = get_app_static_folder(app_name) / js_folder if js_folder else get_app_template_folder(app_name)
    return str(config_path).replace(str(COREHQ_BASE_DIR) + '/', '')


class Command(BaseCommand):
    help = """
    This command builds diffs between files that have undergone the Bootstrap 3 -> Bootstrap 5 Migration split.

    The motivation is to keep track of changes and flag new changes in tests, as the diffs will change
    from what was previously generated by this command. The expectation is that these changes should be propagated
    over to the Bootstrap 5 templates to ensure the two split Bootstrap 3 and Bootstrap 5 templates remain in sync.
    Once the two files are brought up to date, this command can be run again to ensure tests pass.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--update_app',
            help="Specify the app you would like to update the configuration file for.",
        )

    def handle(self, *args, **options):
        update_app = options.get('update_app')

        if has_pending_git_changes():
            self.stdout.write(self.style.ERROR(
                "You have un-committed changes. Please commit these changes before proceeding...\n"
            ))

        if update_app:
            self.update_configuration_file_for_app(update_app)
            return

        clear_diffs_folder()
        full_diff_config = get_bootstrap5_diff_config()
        for bootstrap3_filepath, bootstrap5_filepath, diff_filepath in get_bootstrap5_filepaths(full_diff_config):
            with open(diff_filepath, 'w') as df:
                df.writelines(get_diff(bootstrap3_filepath, bootstrap5_filepath))

        if has_pending_git_changes():
            self.stdout.write(self.style.SUCCESS(
                "\n\nDiffs have been rebuilt. Thank you!\n"
            ))
            self.make_commit("Rebuilt diffs")
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nDone! Diffs are already up-to-date, no changes needed.\n\n"
            ))

    def update_config(self, config, app_name, js_folder=None):
        parent_path = get_parent_path(app_name, js_folder)
        split_folders = get_split_folders(
            get_all_javascript_paths_for_app(app_name) if js_folder is not None
            else get_all_template_paths_for_app(app_name)
        )
        folders = get_relative_folder_paths(parent_path, split_folders)
        folder_configs = [
            get_folder_config(app_name, folder, js_folder)
            for folder in folders
        ]
        if folder_configs:
            config[parent_path] = folder_configs
            self.stdout.write(f"Refreshed config for '{parent_path}'")
        elif parent_path in config:
            del config[parent_path]
            self.stdout.write(f"Removed '{parent_path}' from config. No more relevant files.")

    def check_javascript_paths(self, app_name, js_folders):
        split_js_folders = get_split_folders(get_all_javascript_paths_for_app(app_name))
        untracked_folders = [
            folder for folder in split_js_folders
            if not any([path in folder for path in js_folders])
        ]
        if untracked_folders:
            self.stdout.write("\nThe following javascript folders are untracked:\n")
            self.stdout.write("\n".join(untracked_folders))
            self.stdout.write(
                "\nIf you wish to automatically track them, please update the list of "
                "of `tracked_js_folders`.\n\n\n"
            )

    def update_configuration_file_for_app(self, app_name):
        self.stdout.write(f"\nUpdating configuration file for app '{app_name}'...")
        config_file = get_bootstrap5_diff_config()

        self.update_config(config_file, app_name)
        for js_folder in TRACKED_JS_FOLDERS:
            self.update_config(config_file, app_name, js_folder)
        self.check_javascript_paths(app_name, TRACKED_JS_FOLDERS)
        self.stdout.write("\nSaving config...\n")

        update_bootstrap5_diff_config(config_file)
        has_changes = has_pending_git_changes()
        if has_changes:
            self.stdout.write(self.style.SUCCESS(
                f"{DIFF_CONFIG_FILE} has been updated."
            ))
            self.make_commit(f"Updated diff config for '{app_name}'")
        else:
            self.stdout.write(self.style.SUCCESS(
                "No changes were necessary. Thank you!"
            ))

        self.show_next_steps_after_config_update(show_build_notice=has_changes)

    def show_next_steps_after_config_update(self, show_build_notice=False):
        self.stdout.write(self.style.MIGRATE_LABEL(
            "\n\nPLEASE NOTE: This utility only supports automatically generating a "
            "diff config for template and javascript files.\n"
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Stylesheets (less, scss) must be added to {DIFF_CONFIG_FILE} manually."
        ))

        if show_build_notice:
            self.stdout.write("\n\nAfter committing changes, please re-run:\n\n")
            self.stdout.write(self.style.MIGRATE_HEADING(
                "./manage.py build_bootstrap5_diffs"
            ))
            self.stdout.write("\nto rebuild the diffs.")

        self.stdout.write("\n\nThank you! <3\n\n")

    def make_commit(self, message):
        self.stdout.write("\nNow would be a good time to review changes with git and commit.")
        confirm = get_confirmation("\nAutomatically commit these changes?", default='y')
        if confirm:
            apply_commit(message)
            self.stdout.write(self.style.SUCCESS("\nChanges committed!\n\n"))
            return
        commit_string = get_commit_string(message)
        self.stdout.write("\n\nSuggested command:\n")
        self.stdout.write(self.style.MIGRATE_HEADING(commit_string))
        self.stdout.write("\n")
