from botocore.exceptions import ClientError

from dimagi.utils.retry import retry_on


def retry_on_slow_down(func):
    retry = retry_on(ClientError, should_retry=_is_slow_down,
                     delays=_up_to_two_mins())
    return retry(func)


def _is_slow_down(err: ClientError):
    return (
        'Error' in err.response
        and 'Code' in err.response['Error']
        and err.response['Error']['Code'] == 'SlowDown'
    )


def _up_to_two_mins():
    for x in range(1, 8):
        yield 2 ** x  # 2 to 128
    yield None
