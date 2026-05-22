import pytest

from corehq.apps.celery.serial import get_unique_key


def my_func(domain, count=100):
    pass


def test_constant_format_string():
    key = get_unique_key('some-constant-value', my_func, 'test')
    assert key == 'my_func-some-constant-value'


def test_template_format_string():
    key = get_unique_key('{domain}', my_func, 'test')
    assert key == 'my_func-test'


def test_multiple_template_format_string():
    key = get_unique_key('{domain}-{count}', my_func, 'test', count=99)
    assert key == 'my_func-test-99'


def test_default_value_applied():
    key = get_unique_key('{domain}-{count}', my_func, 'test')
    assert key == 'my_func-test-100'


def test_arg_passed_as_kwarg():
    key = get_unique_key('{domain}-{count}', my_func, domain='test', count=99)
    assert key == 'my_func-test-99'


def test_varargs_function():
    def varargs_fn(*args, **kwargs):
        pass

    key = get_unique_key('{args}', varargs_fn, 1, 2, 3)
    assert key == 'varargs_fn-(1, 2, 3)'

    key = get_unique_key('{kwargs}', varargs_fn, domain='test')
    assert key == "varargs_fn-{'domain': 'test'}"


@pytest.mark.parametrize(
    'args, kwargs',
    [
        (('test', 'extra'), {'count': 1}),
        (('test',), {'invalid': 1}),
    ],
)
def test_raises_type_error_on_signature_mismatch(args, kwargs):
    with pytest.raises(TypeError):
        _ = get_unique_key('constant', my_func, *args, **kwargs)


def test_raises_key_error():
    with pytest.raises(KeyError):
        _ = get_unique_key('{invalid-key}', my_func, 'test', count=99)
