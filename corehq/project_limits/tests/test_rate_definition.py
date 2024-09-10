import math
import random

import pytest
import testil

from corehq.project_limits.rate_limiter import RateDefinition


@pytest.mark.parametrize("_", range(15))
def test_rate_definition_times(_):
    def times_or_none(number_or_none, factor):
        if number_or_none is None:
            return None
        else:
            return number_or_none * factor

    rate_def = _get_random_rate_def()
    factor = int(random.expovariate(1 / 10000))

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


@pytest.mark.parametrize("_", range(15))
def test_rate_definition_with_minimum(_):

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

    base_rate = _get_random_rate_def()
    floor_rate = _get_random_rate_def()
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


@pytest.mark.parametrize("_", range(15))
def test_rate_definition_map(_):
    def preserve_none(fn):
        return lambda x: None if x is None else fn(x)

    rate_def = _get_random_rate_def()
    fn, = random.choices([preserve_none(int),
                          preserve_none(lambda x: x * x),
                          preserve_none(math.exp)])
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


@pytest.mark.parametrize("_", range(15))
def test_rate_definition_map_with_other(_):
    rate_def = _get_random_rate_def()
    fn, = random.choices([lambda x, y: max(filter(None, [x, y, -1])),
                          lambda x, y: None if None in (x, y) else (x * y)])
    other = _get_random_rate_def()
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


def _get_random_rate_def():
    numbers = random.choices([None] + [random.expovariate(1 / 64) for _ in range(6)], k=5)
    return RateDefinition(
        per_second=numbers[0],
        per_minute=numbers[1],
        per_hour=numbers[2],
        per_day=numbers[3],
        per_week=numbers[4],
    )


@pytest.mark.parametrize(
    "n_users, per_second, per_minute, per_hour, per_day, per_week",
    [
        [int(cell.replace(',', '')) for cell in row.split()]
        for row in """
        # of users  second  minute  hour     day        week
        1           1       10      33       73         215
        10          1       10      60       280        1,250
        100         1       17      330      2,350      11,600
        1000        6       80      3,030    23,050     115,100
        10000       51      710     30,030   230,050    1,150,100
        100000      501     7,010   300,030  2,300,050  11,500,100
        """.strip().splitlines()[1:]
    ],
)
def test_rate_definition_against_fixed_user_table(n_users, per_second, per_minute, per_hour, per_day, per_week):
    per_user_rate = RateDefinition(
        per_week=115,
        per_day=23,
        per_hour=3,
        per_minute=0.07,
        per_second=0.005,
    )
    floor_rate = RateDefinition(
        per_week=100,
        per_day=50,
        per_hour=30,
        per_minute=10,
        per_second=1,
    )

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
