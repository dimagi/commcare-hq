from corehq.apps.hqwebapp.management.commands.build_bootstrap5_diffs import (
    get_bootstrap5_diff_config,
    get_bootstrap5_filepaths,
    get_diff,
    COREHQ_BASE_DIR,
    get_parent_path,
    get_relative_folder_paths,
    get_folder_config,
)

from testil import eq

FAILURE_MESSAGE = """"


******************************************
* Bootstrap 5 Migrated File Diff Failure *
******************************************

Please make sure that when you edit a Bootstrap 3 or Bootstrap 5 migrated file
that you apply any relevant changes to BOTH split files.

Once you are done syncing the changes in these files, please run
```
./manage.py build_bootstrap5_diffs
```
to regenerate the diff outputs so that tests pass again. Thank you!

The following pairs of files failed the Bootstrap 3 -> 5 diff check:
{}

*******************************************


"""


def test_that_diffs_of_migrated_files_match_expected_outputs():
    """
    When this test fails, it is a reminder to keep Bootstrap 3 -> 5 migrated files in sync.
    Once the files are in sync, run the "build_bootstrap5_diffs" management
    command to regenerate the diffs.
    """
    full_diff_config = get_bootstrap5_diff_config()
    unexpected_diffs = []
    for bootstrap3_filepath, bootstrap5_filepath, diff_filepath in get_bootstrap5_filepaths(full_diff_config):
        current_diff = get_diff(bootstrap3_filepath, bootstrap5_filepath)
        with open(diff_filepath, 'r') as df:
            expected_diff = [line.rstrip() for line in df.readlines()]
            current_diff = [line.rstrip() for line in current_diff]
            if "".join(current_diff) != "".join(expected_diff):
                unexpected_diffs.append([
                    str(bootstrap3_filepath).replace(str(COREHQ_BASE_DIR), ''),
                    str(bootstrap5_filepath).replace(str(COREHQ_BASE_DIR), '')
                ])

    failed_file_list = [f"{f[0]} > {f[1]}" for f in unexpected_diffs]
    eq(unexpected_diffs, [], text=FAILURE_MESSAGE.format("\n".join(failed_file_list)))


def test_get_parent_path_for_templates():
    parent_path = get_parent_path("hqwebapp")
    eq(parent_path, "apps/hqwebapp/templates/hqwebapp")


def test_get_parent_path_for_javascript():
    parent_path = get_parent_path("hqwebapp", js_folder="js")
    eq(parent_path, "apps/hqwebapp/static/hqwebapp/js")


def test_get_relative_folder_paths():
    config_path = "apps/hqwebapp/templates/hqwebapp"
    migrated_paths = {
        '/apps/hqwebapp/templates/hqwebapp/crispy',
        '/apps/hqwebapp/templates/hqwebapp',
        '/apps/hqwebapp/templates/hqwebapp/partials',
        '/apps/hqwebapp/templates/hqwebapp/includes'
    }
    eq(
        get_relative_folder_paths(config_path, migrated_paths),
        ['', 'crispy', 'includes', 'partials']
    )


def test_get_relative_folder_paths_gets_relevant_paths_only():
    config_path = "apps/hqwebapp/static/hqwebapp/js"
    migrated_paths = {
        '/apps/hqwebapp/static/hqwebapp/js/components',
        '/apps/hqwebapp/static/hqwebapp/spec',
        '/apps/hqwebapp/static/hqwebapp/js',
        '/apps/hqwebapp/static/hqwebapp/js/ui_elements'
    }
    eq(
        get_relative_folder_paths(config_path, migrated_paths),
        ['', 'components', 'ui_elements']
    )


def test_get_folder_config_for_templates():
    folder_config = get_folder_config("hqwebapp", "partials")
    eq(
        folder_config,
        {
            "directories": ["partials/bootstrap3", "partials/bootstrap5"],
            "file_type": "template",
            "label": "hqwebapp/partials",
            "compare_all_files": True,
        }
    )


def test_get_folder_config_for_javascript():
    folder_config = get_folder_config(
        "hqwebapp", "components", js_folder="js"
    )
    eq(
        folder_config,
        {
            "directories": ["components/bootstrap3", "components/bootstrap5"],
            "file_type": "javascript",
            "label": "javascript/hqwebapp/js/components",
            "compare_all_files": True,
        }
    )
