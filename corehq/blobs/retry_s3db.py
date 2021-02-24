from botocore.exceptions import ClientError

from dimagi.utils.retry import retry_on


def retry_on_slow_down(func):
    retry = retry_on(ClientError, should_retry=_is_slow_down,
                     delays=(1, 2, 4, 8, 16, 32, 64, 128))
    return retry(func)


def _is_slow_down(err: ClientError):
    return (
        'Error' in err.response
        and 'Code' in err.response['Error']
        and err.response['Error']['Code'] == 'SlowDown'
    )
