import math
import random

import testil
from mock import mock

from corehq.project_limits.rate_limiter import RateLimiter, RateDefinition, \
    PerUserRateDefinition


@mock.patch('corehq.project_limits.rate_limiter.get_user_count', lambda domain: 10)
def test_rate_limit_interface():
    """
    Just test that very basic usage doesn't error
    """
    per_user_rate_def = RateDefinition(per_week=50000, per_day=13000, per_second=.001)
    min_rate_def = RateDefinition(per_second=10)
    per_user_rate_def = PerUserRateDefinition(per_user_rate_def, min_rate_def)
    my_feature_rate_limiter = RateLimiter('my_feature', per_user_rate_def.get_rate_limits)
    if my_feature_rate_limiter.allow_usage('my_domain'):
        # ...do stuff...
        my_feature_rate_limiter.report_usage('my_domain')


def test_rate_definition_times():
    def times_or_none(number_or_none, factor):
        if number_or_none is None:
            return None
        else:
            return number_or_none * factor
    for _ in range(15):
        numbers = random.choices([None] + [random.expovariate(1/64) for _ in range(6)], k=5)
        factor = int(random.expovariate(1/10000))
        testil.eq(
            RateDefinition(
                per_second=numbers[0],
                per_minute=numbers[1],
                per_hour=numbers[2],
                per_day=numbers[3],
                per_week=numbers[4],
            ).times(factor),
            RateDefinition(
                per_second=times_or_none(numbers[0], factor),
                per_minute=times_or_none(numbers[1], factor),
                per_hour=times_or_none(numbers[2], factor),
                per_day=times_or_none(numbers[3], factor),
                per_week=times_or_none(numbers[4], factor),
            ),
        )


def test_rate_definition_with_minimum():
    def asymmetric_max(base_number_or_none, floor_number_or_none):
        """
        Return max of the two numbers with the None value being treated asymmetrically

        None means:
          - Infinity for the base value
          - Negative Infinity for the floor value
          - Infinity in the return value

        This corresponds to the intuitive notion that None in a rate limit value means
        "Not imposing a limit" and None in a floor value means "Not imposing a floor".

        (This function is only meant to be used with positive numbers,
        but will work with with negative numbers and zero as well
        which are meaningless in the context of rate limiting.)
        """
        if base_number_or_none is None:  # "Infinity"
            return None  # "Infinity"
        elif floor_number_or_none is None:  # "Negative Infinity"
            return base_number_or_none
        else:
            return max(base_number_or_none, floor_number_or_none)

    for _ in range(15):
        base_numbers = random.choices([None] + [random.expovariate(1/64) for _ in range(6)], k=5)
        floor_numbers = random.choices([None] + [random.expovariate(1/64) for _ in range(6)], k=5)
        testil.eq(
            RateDefinition(
                per_second=base_numbers[0],
                per_minute=base_numbers[1],
                per_hour=base_numbers[2],
                per_day=base_numbers[3],
                per_week=base_numbers[4],
            ).with_minimum(RateDefinition(
                per_second=floor_numbers[0],
                per_minute=floor_numbers[1],
                per_hour=floor_numbers[2],
                per_day=floor_numbers[3],
                per_week=floor_numbers[4],
            )),
            RateDefinition(
                per_second=asymmetric_max(base_numbers[0], floor_numbers[0]),
                per_minute=asymmetric_max(base_numbers[1], floor_numbers[1]),
                per_hour=asymmetric_max(base_numbers[2], floor_numbers[2]),
                per_day=asymmetric_max(base_numbers[3], floor_numbers[3]),
                per_week=asymmetric_max(base_numbers[4], floor_numbers[4]),
            )
        )


def test_rate_definition_map():
    def preserve_none(fn):
        return lambda x: None if x is None else fn(x)

    for _ in range(15):
        numbers = random.choices([None] + [random.expovariate(1/64) for _ in range(6)], k=5)
        fn, = random.choices([preserve_none(int),
                              preserve_none(lambda x: x * x),
                              preserve_none(math.exp)])
        testil.eq(
            RateDefinition(
                per_second=numbers[0],
                per_minute=numbers[1],
                per_hour=numbers[2],
                per_day=numbers[3],
                per_week=numbers[4],
            ).map(fn),
            RateDefinition(
                per_second=fn(numbers[0]),
                per_minute=fn(numbers[1]),
                per_hour=fn(numbers[2]),
                per_day=fn(numbers[3]),
                per_week=fn(numbers[4]),
            ),
        )


def test_rate_definition_map_with_other():
    for _ in range(15):
        numbers = random.choices([None] + [random.expovariate(1/64) for _ in range(6)], k=5)
        fn, = random.choices([lambda x, y: max(filter(None, [x, y, -1])),
                              lambda x, y: None if None in (x, y) else (x * y)])
        other_numbers = random.choices([None] + [random.expovariate(1 / 64) for _ in range(6)], k=5)
        testil.eq(
            RateDefinition(
                per_second=numbers[0],
                per_minute=numbers[1],
                per_hour=numbers[2],
                per_day=numbers[3],
                per_week=numbers[4],
            ).map(fn, RateDefinition(
                per_second=other_numbers[0],
                per_minute=other_numbers[1],
                per_hour=other_numbers[2],
                per_day=other_numbers[3],
                per_week=other_numbers[4],
            )),
            RateDefinition(
                per_second=fn(numbers[0], other_numbers[0]),
                per_minute=fn(numbers[1], other_numbers[1]),
                per_hour=fn(numbers[2], other_numbers[2]),
                per_day=fn(numbers[3], other_numbers[3]),
                per_week=fn(numbers[4], other_numbers[4]),
            ),
        )


def test_rate_definition_against_fixed_user_table():
    tab_delimited_table = """
    # of users	second	minute	hour	day	week
    1	1	10	30	50	115
    10	1	10	30	230	1,150
    100	1	10	300	2,300	11,500
    1000	5	70	3,000	23,000	115,000
    10000	50	700	30,000	230,000	1,150,000
    100000	500	7,000	300,000	2,300,000	11,500,000
    """

    rows = tab_delimited_table.strip().splitlines()[1:]
    table = [[int(cell.replace(',', '')) for cell in row.split('\t')] for row in rows]
    per_user_rate = RateDefinition(
        per_week=115,
        per_day=23,
        per_hour=3,
        per_minute=0.07,
        per_second=0.005,
    )
    floor_rate = RateDefinition(
        per_day=50,
        per_hour=30,
        per_minute=10,
        per_second=1,
    )
    for n_users, per_second, per_minute, per_hour, per_day, per_week in table:
        testil.eq(
            per_user_rate.times(n_users).with_minimum(floor_rate).map(int),
            RateDefinition(
                per_week=per_week,
                per_day=per_day,
                per_hour=per_hour,
                per_minute=per_minute,
                per_second=per_second,
            ),
        )
