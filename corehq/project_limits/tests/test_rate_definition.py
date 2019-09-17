import math
import random

import testil

from corehq.project_limits.rate_limiter import RateDefinition


def test_rate_definition_times():
    def check(rate_def, factor):
        testil.eq(
            rate_def.times(factor),
            RateDefinition(
                per_second=times_or_none(rate_def.per_second, factor),
                per_minute=times_or_none(rate_def.per_minute, factor),
                per_hour=times_or_none(rate_def.per_hour, factor),
                per_day=times_or_none(rate_def.per_day, factor),
                per_week=times_or_none(rate_def.per_week, factor),
            ),
        )

    def times_or_none(number_or_none, factor):
        if number_or_none is None:
            return None
        else:
            return number_or_none * factor

    for _ in range(15):
        rate_def = _get_random_rate_def()
        factor = int(random.expovariate(1 / 10000))
        yield check, rate_def, factor


def test_rate_definition_with_minimum():

    def check(base_rate, floor_rate):
        testil.eq(
            base_rate.plus(floor_rate),
            RateDefinition(
                per_second=asymmetric_sum(base_rate.per_second, floor_rate.per_second),
                per_minute=asymmetric_sum(base_rate.per_minute, floor_rate.per_minute),
                per_hour=asymmetric_sum(base_rate.per_hour, floor_rate.per_hour),
                per_day=asymmetric_sum(base_rate.per_day, floor_rate.per_day),
                per_week=asymmetric_sum(base_rate.per_week, floor_rate.per_week)
            )
        )

    def asymmetric_sum(base_number_or_none, incr_number_or_none):
        """
        Return sum of the two numbers with the None value being treated asymmetrically

        None means:
          - Infinity for the base value
          - 0 for the incr value
          - Infinity in the return value

        This corresponds to the intuitive notion that None in a rate limit value means
        "Not imposing a limit" and None in an incr value means "Not incrementing the limit".
        """
        if base_number_or_none is None:  # "Infinity"
            return None  # "Infinity"
        elif incr_number_or_none is None:  # "0"
            return base_number_or_none
        else:
            return base_number_or_none + incr_number_or_none

    for _ in range(15):
        base_rate = _get_random_rate_def()
        incr_rate = _get_random_rate_def()
        yield check, base_rate, incr_rate


def test_rate_definition_map():
    def check(rate_def, fn):
        testil.eq(
            rate_def.map(fn),
            RateDefinition(
                per_second=fn(rate_def.per_second),
                per_minute=fn(rate_def.per_minute),
                per_hour=fn(rate_def.per_hour),
                per_day=fn(rate_def.per_day),
                per_week=fn(rate_def.per_week),
            ),
        )

    def preserve_none(fn):
        return lambda x: None if x is None else fn(x)

    for _ in range(15):
        rate_def = _get_random_rate_def()
        fn, = random.choices([preserve_none(int),
                              preserve_none(lambda x: x * x),
                              preserve_none(math.exp)])
        yield check, rate_def, fn


def test_rate_definition_map_with_other():
    def check(rate_def, fn, other):
        testil.eq(
            rate_def.map(fn, other),
            RateDefinition(
                per_second=fn(rate_def.per_second, other.per_second),
                per_minute=fn(rate_def.per_minute, other.per_minute),
                per_hour=fn(rate_def.per_hour, other.per_hour),
                per_day=fn(rate_def.per_day, other.per_day),
                per_week=fn(rate_def.per_week, other.per_week),
            ),
        )

    for _ in range(15):
        rate_def = _get_random_rate_def()
        fn, = random.choices([lambda x, y: max(filter(None, [x, y, -1])),
                              lambda x, y: None if None in (x, y) else (x * y)])
        other = _get_random_rate_def()
        yield check, rate_def, fn, other


def _get_random_rate_def():
    numbers = random.choices([None] + [random.expovariate(1 / 64) for _ in range(6)], k=5)
    return RateDefinition(
        per_second=numbers[0],
        per_minute=numbers[1],
        per_hour=numbers[2],
        per_day=numbers[3],
        per_week=numbers[4],
    )


def test_rate_definition_against_fixed_user_table():
    tab_delimited_table = """
    # of users  second  minute  hour    day       week
    1           1       10      33      73        115
    10          1       10      60      280       1,150
    100         1       17      330     2,350     11,500
    1000        6       80      3,030   23,050    115,000
    10000       51      710     30,030  230,050   1,150,000
    100000      501     7,010   300,030 2,300,050 11,500,000
    """

    rows = tab_delimited_table.strip().splitlines()[1:]
    table = [[int(cell.replace(',', '')) for cell in row.split()] for row in rows]
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
            per_user_rate.times(n_users).plus(floor_rate).map(int),
            RateDefinition(
                per_week=per_week,
                per_day=per_day,
                per_hour=per_hour,
                per_minute=per_minute,
                per_second=per_second,
            ),
        )
