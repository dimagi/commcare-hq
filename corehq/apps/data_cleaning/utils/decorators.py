import time
from django.db import IntegrityError


def retry_on_integrity_error(max_retries=3, delay=0.1):
    """
    Decorator to retry a function call if an IntegrityError occurs.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except IntegrityError:
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator
