"""
These functions need to be callable from both the management command and the view
"""
from itertools import chain
from django.conf import settings
from corehq.apps.app_tester.client import FormPlayerApiClient


class TestComplete(Exception):
    """
    Used to stop a test once an outcome has been reached
    """
    pass


def put_name_key_in_value(dict_):
    """
    What looks nice in YAML doesn't look so nice in Python. Fix that by
    putting the key of a single key-value pair into its value as "name".

    >>> put_name_key_in_value({'some name': {'foo': 1, 'bar': 2}})
    {'name': 'some name', 'foo': 1, 'bar': 2}

    """
    if len(dict_) != 1:
        raise ValueError('A single key-value pair expected')
    key = dict_.keys()[0]
    if dict_.get('name'):
        raise ValueError('Value already has a name')
    return dict(dict_[key], name=key)


def test_form(form_dict, client, login_data):
    test_result = {}
    with client.form_session(
        login_data['domain'],
        login_data['username'],
        form_dict['name'],  # This is an XMLNS. TODO: Look up XMLNS from name
        case_id=None
    ) as session:
        answer = None
        while True:
            try:
                responses = session.submit_answer(answer)
            except Exception as err:
                test_result['exception'] = err
                raise TestComplete
            else:
                if any(r.is_error for r in responses):
                    test_result['errors'] = [r for r in responses if r.is_error]
                else:
                    question = responses[-1]
                    answer = form_dict['answers'][question]
    return test_result


def pass_test(name, verbosity):
    if verbosity == 1:
        return '.'
    elif verbosity > 1:
        return name + ': PASS\n'


def error_test(name, error_msg, verbosity):
    error = (
        'ERROR: {}\n'
        'Error message: {}\n'.format(name, error_msg)
    )
    if verbosity == 1:
        return 'E', error
    elif verbosity > 1:
        return name + ': ERROR\n', error


def fail_test(name, expected, got, verbosity):
    failure = (
        'FAILURE: {}\n'
        'Expected: {}\n'
        'Got: {}\n'.format(name, expected, got)
    )
    if verbosity == 1:
        return 'F', failure
    elif verbosity > 1:
        return name + ': FAIL\n', failure


def get_error_msg(error_response):
    """
    Tries to get an error message out of an XformsResponse
    """
    if error_response.error:
        return error_response.error
    return getattr(error_response, 'text_prompt', '')


def evaluate_result(test_dict, test_result, verbosity):
    """
    If the test ran through: test_result == {}.
    If the test encountered an exception: test_result == {'exception': Exception instance}
    If the test errorred: test_result == {'errors': [list of error responses returned by touchforms API]}
    """
    error = failure = None
    what_we_want = test_dict['result']
    if test_result is None:
        # Cataclysmic failure: Not a single question was tested. Tester broke.
        raise ValueError('Unable to execute test: \n{}'.format(test_dict))
    elif 'errors' in test_result:
        what_we_got = ('failure', 'error')
    elif 'exception' in test_result:
        what_we_got = ('failure', 'error', 'exception')
    else:
        assert test_result == {}  # Test completed without errors or exceptions
        what_we_got = ('success',)

    if what_we_want in what_we_got:
        if what_we_want in ('success', 'failure'):
            result = pass_test(test_dict['name'], verbosity)
        elif what_we_want == 'exception':
            if 'exception' in test_dict:
                if test_dict['exception'] in repr(test_result['exception']):
                    result = pass_test(test_dict['name'], verbosity)
                else:
                    # We expected an exception, but we got a different one. Fail, don't error
                    result, failure = fail_test(
                        name=test_dict['name'],
                        expected=repr(test_result['exception']),
                        got=test_result['exception'],
                        verbosity=verbosity
                    )
            else:
                result = pass_test(test_dict['name'], verbosity)
        else:
            assert what_we_want == 'error'
            if 'error' in test_dict:
                if any(test_dict['error'] in get_error_msg(e) for e in test_result['errors']):
                    result = pass_test(test_dict['name'], verbosity)
                else:
                    # We expected an error, but we got a different one. Fail, don't error
                    got = ', '.join(get_error_msg(e) for e in test_result['errors'])
                    result, failure = fail_test(
                        name=test_dict['name'],
                        expected=test_dict['error'],
                        got=got,
                        verbosity=verbosity
                    )
            else:
                result = pass_test(test_dict['name'], verbosity)
    else:
        if 'exception' in what_we_got:
            result, error = error_test(test_dict['name'], repr(test_result['exception']), verbosity)
        elif 'error' in what_we_got:
            got = ', '.join(get_error_msg(e) for e in test_result['errors'])
            result, error = error_test(test_dict['name'], got, verbosity)
        else:
            assert what_we_got == ('success',)
            result, failure = fail_test(
                name=test_dict['name'],
                expected=what_we_want,
                got='success',
                verbosity=verbosity
            )
    return result, error, failure


def run_test(test_data, login_data, return_result, verbosity=1):
    # TODO: Validate test_data
    client = FormPlayerApiClient(
        host=settings.XFORMS_PLAYER_URL,
        username=settings.TOUCHFORMS_API_USER,
        password=settings.TOUCHFORMS_API_PASSWORD
    )
    test_dict = put_name_key_in_value(test_data)
    test_result = None
    try:
        for module in test_dict['modules']:
            module_dict = put_name_key_in_value(module)
            # Ignore cases for MVP
            for form in module_dict['forms']:
                form_dict = put_name_key_in_value(form)
                test_result = test_form(form_dict, client, login_data)
    except TestComplete:
        pass
    result, error, failure = evaluate_result(test_dict, test_result, verbosity)
    if return_result:
        return result, error, failure
    else:
        print result,
        return error, failure


def print_errors_failures(results):
    """
    Print errors first, and then failures
    """
    def print_sep():
        print '-' * 80

    errors = (e for e, f in results if e)
    failures = (f for e, f in results if f)
    for e_f in chain(errors, failures):
        print_sep()
        print e_f


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
    else:
        print_errors_failures(results)
