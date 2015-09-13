from functools import wraps

from fabric.api import env
import requests


def chief_hook(name):
    def decorator(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            if env.is_chief_deploy:
                requests.post('{}/hq/system/chief/process_hook'.format(env.url), params={
                    'name': name,
                })
            return fn(*args, **kwargs)
        return inner
    return decorator
