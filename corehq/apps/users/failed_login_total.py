from datetime import datetime
from django_redis import get_redis_connection

ONE_DAY = 60 * 60 * 24
EPOCH_TS = 0
EPOCH = datetime.utcfromtimestamp(EPOCH_TS)


class FailedLoginTotal:
    """A thread-safe class to record login failures."""

    FIELD_FAILURES = 'failures'
    FIELD_TS = 'ts'

    @classmethod
    def get(cls, username):
        raw_failures, raw_ts = cls._get_raw_fields(username)
        last_attempt_time = cls._to_time(raw_ts)
        num_failures = int(raw_failures or 0)

        return cls(username, num_failures, last_attempt_time)

    @classmethod
    def _get_raw_fields(cls, username):
        redis_client = get_redis_connection()
        return redis_client.hmget(cls._get_key(username), cls.FIELD_FAILURES, cls.FIELD_TS)

    @staticmethod
    def _get_key(username):
        return f'attempts_{username}'

    @staticmethod
    def _to_time(raw_ts):
        timestamp = float(raw_ts or EPOCH_TS)
        return datetime.utcfromtimestamp(timestamp)

    def __init__(self, username, failures=0, last_attempt_time=EPOCH):
        self.username = username
        self._reset_values(failures, last_attempt_time)

        self.key = self._get_key(self.username)

    def _reset_values(self, failures=0, last_attempt_time=EPOCH):
        self.failures = failures
        self.last_attempt_time = last_attempt_time

    def clear(self):
        redis_client = get_redis_connection()
        redis_client.delete(self.key)

        self._reset_values()

    def add_failure(self, current_time):
        redis_client = get_redis_connection()
        transaction_results = redis_client.transaction(
            self._create_failure_handler(current_time),
            self.key)
        num_failures = transaction_results[0] or 1

        self._reset_values(failures=num_failures, last_attempt_time=current_time)

        return num_failures

    def _create_failure_handler(self, current_time):
        def add_failure(pipe):
            previous_attempt_time = self._to_time(pipe.hget(self.key, self.FIELD_TS))

            pipe.multi()

            # NOTE: there is a race condition here, where we could receive the current date first,
            # then a previous date. The database would get updated with the previous date,
            # and the user is likely to have his login failures reset multiple times.
            # Viewing this as an acceptable risk for now.
            # It would be hard for anyone to game this, and the worst that would happen is they'd
            # be able to achieve 2-3x the maximum allowable failures.
            if previous_attempt_time.date() != current_time.date():
                # Reset failures when a new day begins
                pipe.hset(self.key, self.FIELD_FAILURES, 1)
            else:
                pipe.hincrby(self.key, self.FIELD_FAILURES, 1)

            pipe.hset(self.key, self.FIELD_TS, current_time.timestamp())
            pipe.expire(self.key, ONE_DAY)

        return add_failure

    def __repr__(self):
        return f'{self.username}: {self.failures} failures, last at {self.last_attempt_time}'
