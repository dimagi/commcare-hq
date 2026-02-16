from functools import wraps

import requests

from corehq.apps.celery.shared_task import task


def analytics_task(
    default_retry_delay=10,
    max_retries=3,
    queue='analytics_queue',
    serializer='json',
    durable=False,
):
    """
    Defines a task that posts data to one of our analytics endpoints. It
    retries the task up to 3 times if the post returns with a status code
    indicating an error with the post that is not our fault.
    """

    def decorator(func):
        @task(
            bind=True,
            queue=queue,
            ignore_result=True,
            acks_late=True,
            default_retry_delay=default_retry_delay,
            max_retries=max_retries,
            serializer=serializer,
            durable=durable,
        )
        @wraps(func)
        def _inner(self, *args, **kwargs):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                # if bad request, raise exception because it is our fault
                res = e.response
                status_code = (
                    res.status_code
                    if isinstance(res, requests.models.Response)
                    else res.status
                )
                if status_code == 400:
                    raise
                else:
                    self.retry(exc=e)

        return _inner

    return decorator
