import inspect


def tag_with_no_domain(fn):
    all_args = inspect.getfullargspec(inspect.unwrap(fn)).args
    assert not ('domain' in all_args or 'domain_name' in all_args)

    fn._tag_with_no_domain = True
    return fn
