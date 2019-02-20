from collections import Counter

from corehq.sql_db.util import weighted_choice


def test_weighted_choice():
    """
    Run weighted_choice() 6000 times, and check results are roughly what
    we would expect.
    """
    choices = ['one_half', 'one_third', 'one_sixth']
    weights = [1.0/2, 1.0/3, 1.0/6]
    results = [weighted_choice(choices, weights) for __ in range(6000)]
    counter = Counter(results)
    count_by_choice = dict(counter.most_common())
    assert 2500 < count_by_choice['one_half'] < 3500, \
        'Expected half of 6000 to be roughly 3000. Was {}.'.format(count_by_choice['one_half'])
    assert 1500 < count_by_choice['one_third'] < 2500, \
        'Expected a third of 6000 to be roughly 2000. Was {}.'.format(count_by_choice['one_third'])
    assert 500 < count_by_choice['one_sixth'] < 1500, \
        'Expected a sixth of 6000 to be roughly 1000. Was {}.'.format(count_by_choice['one_sixth'])
