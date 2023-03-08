from corehq.apps.hqwebapp.management.commands.build_bootstrap5_diffs import (
    get_bootstrap5_diff_config,
    get_bootstrap5_filepaths,
    get_diff,
    COREHQ_BASE_DIR,
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
