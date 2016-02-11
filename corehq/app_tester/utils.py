"""
These functions need to be callable from both the management command and the view
"""
from django.conf import settings

from corehq.app_tester.client import FormPlayerApiClient


def put_key_in_value(dict_):
    """
    What looks nice in YAML doesn't look so nice in Python. Fix that.

    >>> get_name_value({'some name': {'foo': 1, 'bar': 2}})
    {'name': 'some name', 'foo': 1, 'bar': 2}

    """
    if len(dict_) != 1:
        raise ValueError('A single key-value pair expected')
    key = dict_.keys()[0]
    if dict_.get('name'):
        raise ValueError('Value already have a name')
    return dict(dict_[key], name=key)


def run_test(test_data, login_data, return_results=False, verbosity=1):
    client = FormPlayerApiClient(
        host=settings.XFORMS_PLAYER_URL,
        username=settings.TOUCHFORMS_API_USER,
        password=settings.TOUCHFORMS_API_PASSWORD
    )
    test_dict = put_key_in_value(test_data)
    for module in test_dict['modules']:
        module_dict = put_key_in_value(module)
        # Ignore cases for MVP
        for form in module_dict['forms']:
            session = client.open_form_session(
                login_data['domain'],
                login_data['username'],
                form['name'],  # in MVP. TODO: Look up XMLNS from name
                lang=login_data.get('lang', 'en')
            )
            for question in session.iter_questions():
                try:
                    result = session.submit_answer(question, form['answers'][question])
                except Exception as err:
                    # TODO: Keep err
                    pass
                # TODO: Keep result
    # TODO: Evaluate test result against assertion
    # TODO: Return result


def run_tests(data, return_results=False, verbosity=1):
    """
    Run tests

    :param data: Data describing connection details, tests and expected results
    :param return_results: Return results as a return value. Else print.
    :param verbosity: 1: Print fullstops. 2. Print details
    :return: Test results if return_results is True
    """
    results = []
    for test in data['tests']:
        results.append(run_test(test, data['login'], return_results, verbosity))
    if return_results:
        return results
