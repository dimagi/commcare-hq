from django.utils.translation import gettext_lazy

from corehq.apps.case_importer.tracking.task_status import (
    make_task_status_success,
    normalize_task_status_result_errors,
)


def _result(column_name):
    return {
        'match_count': 0,
        'created_count': 0,
        'num_chunks': 0,
        'errors': {
            'Invalid Parent ID': {
                column_name: {
                    'error': 'Invalid Parent ID',
                    'description': 'something went wrong',
                    'rows': [2],
                }
            }
        },
    }


def test_normalize_errors_with_string_column():
    [error] = normalize_task_status_result_errors(_result('parent_id'))
    assert error.column == 'parent_id'


def test_normalize_errors_with_lazy_column_does_not_raise():
    # Regression: SAAS-19947. A gettext_lazy proxy used to leak into
    # error.column_name when an exception was raised with the message in
    # the positional column_name slot. The strict StringProperty on
    # TaskStatusResultError.column then rejected the proxy and the celery
    # task failed before it could persist the result.
    lazy_column = gettext_lazy("Invalid value for 'parent_relationship_type' column")
    [error] = normalize_task_status_result_errors(_result(lazy_column))
    assert error.column == str(lazy_column)


def test_normalize_errors_with_none_column():
    [error] = normalize_task_status_result_errors(_result(None))
    assert error.column == ''


def test_make_task_status_success_wraps_result():
    status = make_task_status_success(_result('parent_id'))
    assert status.is_finished()
    [error] = status.result.errors
    assert error.column == 'parent_id'
