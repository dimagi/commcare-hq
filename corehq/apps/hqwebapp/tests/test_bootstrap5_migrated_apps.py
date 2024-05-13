from testil import eq

from corehq.apps.hqwebapp.management.commands.show_invalid_bootstrap3_files import get_app_issues

FAILURE_MESSAGE = """


**********************************************************
* Un-migrated Bootstrap 3 Files Exist in Bootstrap 5 App *
**********************************************************

There exist invalid files in apps that have either completed a
Bootstrap 5 migration or are in progress with a migration.

These files are invalid when:

A) A Bootstrap 3 reference exists in a file within an app, but the app
has already been marked as having completed a Bootstrap 5 migration.

B) A Bootstrap 3 reference exists in a file within an app, but the file is
not in a split-files directory and the app has a Bootstrap 5 migration in
progress.

The following apps have issues:

{}

You can run the following command to get additional details and next steps:
```
./manage.py show_invalid_bootstrap3_files
```

*******************************************

"""


def _display_app_issues(app_issues):
    error_list = []
    for issue in app_issues:
        template_issues = issue[1].get("templates", [])
        javascript_issues = issue[1].get("javascript_issues", [])
        total_issues = len(template_issues) + len(javascript_issues)
        error_list.append(
            f"\t{issue[0]}: {total_issues} issue(s)"
        )
    return "\n".join(error_list)


def test_that_new_templates_added_to_migrated_apps_are_not_bootstrap3():
    """
    When this test fails, it means that new templates or javascript files have been added
    to apps that have been touched by the Bootstrap 5 Migration and these templates
    still reference Bootstrap 3 dependencies.
    """
    app_issues = get_app_issues()
    eq(app_issues, [], text=FAILURE_MESSAGE.format(_display_app_issues(app_issues)))
