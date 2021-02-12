from datetime import datetime
from django_redis import get_redis_connection

ONE_DAY = 60 * 60 * 24
EPOCH = datetime.utcfromtimestamp(0)


class LoginRecord:
    """A thread-safe class to record login failures."""

    FIELD_FAILURES = 'failures'
    FIELD_TS = 'ts'

    @classmethod
    def get(cls, username):
        raw_failures, raw_ts = cls._get_raw_fields(username)
        attempts_ts = float(raw_ts or 0)
        num_failures = int(raw_failures or 0)

        last_attempt_date = datetime.utcfromtimestamp(attempts_ts)

        return cls(username, num_failures, last_attempt_date)

    @classmethod
    def _get_raw_fields(cls, username):
        redis_client = get_redis_connection()
        return redis_client.hmget(cls._get_key(username), cls.FIELD_FAILURES, cls.FIELD_TS)

    @staticmethod
    def _get_key(username):
        return f'attempts_{username}'

    def __init__(self, username, failures=0, last_attempt_date=EPOCH):
        self.username = username
        self._reset_values(failures, last_attempt_date)

        self.key = self._get_key(self.username)

    def _reset_values(self, failures=0, last_attempt_date=EPOCH):
        self.failures = failures
        self.last_attempt_date = last_attempt_date

    def clear(self):
        redis_client = get_redis_connection()
        redis_client.delete(self.key)

        self._reset_values()

    def add_failure(self, current_time):
        redis_client = get_redis_connection()
        transaction_results = redis_client.transaction(
            self._create_failure_handler(current_time),
            self.key)
        num_failures = transaction_results[0]

        if num_failures is True:
            num_failures = 1

        self._reset_values(failures=num_failures, last_attempt_date=current_time)

        return num_failures

    def _create_failure_handler(self, current_time):
        def add_failure(pipe):
            previous_attempt_ts = float(pipe.hget(self.key, self.FIELD_TS) or 0)
            previous_attempt_date = datetime.utcfromtimestamp(previous_attempt_ts).date()

            time_between_attempts = current_time.date() - previous_attempt_date

            pipe.multi()

            if time_between_attempts.days >= 1:
                pipe.hset(self.key, self.FIELD_FAILURES, 1)
            else:
                pipe.hincrby(self.key, self.FIELD_FAILURES, 1)

            pipe.hset(self.key, self.FIELD_TS, current_time.timestamp())
            pipe.expire(self.key, ONE_DAY)

        return add_failure

    def __repr__(self):
        return f'{self.username}: {self.attempts} failures, last at: {self.last_attempt_date}'
