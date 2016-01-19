Fluff
=====
Fluff is a library that works with pillowtop and couchdbkit and
lets you define a set of computations to do
on all docs of a `doc_type`, i.e. perform a map over them, and then use
couchdb to aggregate over the output.

The advantages of this over a normal map reduce are that you get to write
your map in python with full access to the database.

This document describes the intended capabilities;
what's currently here is very preliminary.

Example:

```python

import fluff

class VisitCalculator(fluff.Calculator):

    @fluff.date_emitter
    def all_visits(self, case):
        for action in case.actions:
            yield action.date

    @fluff.date_emitter
    def bp_visits(self, case):
        for action in case.actions:
            if is_bp(case):
                yield action.date

    @fluff.custom_date_emitter('max')
    def temp_max(self, case):
        for action in case.actions:
            if is_temp(case):
                yield [action.date, action.temperature]
    
    @fluff.date_emitter
    def group_list(self, case):
        # Note that you can override the group_by values as follows.
        # They MUST always match up in number and ordering to what is defined
        # in the IndicatorDocument class that this calculator is included in.
        yield dict(date=date(2013, 1, 1), value=3, group_by=['abc', 'xyz'])


class MyIndicators(fluff.IndicatorDocument):
    document_class = CommCareCase
    group_by = (
        # this is the standard style of group_by
        'domain',
        # this is the more complicated style of group_by - redundant here,
        # but useful for more complex things
        # note: if you use anything more complicated than a string (like here),
        # group_by should be a tuple, else couchdbkit will complain
        fluff.AttributeGetter('owner_id', getter_function=lambda item: item['owner_id']),
    )
    domains = ('droberts', 'test', 'corpora')

    visits_week = VisitCalculator(window=timedelta(days=7))
    visits_month = VisitCalculator(window=timedelta(days=30))


# add this pillow to settings.PILLOWTOPS
MyIndicatorsPillow = MyIndicators.pillow()

```

By creating a simple setup of this sort, you'll get a bunch of stuff for free:

* Whenever a doc changes, the corresponding indicator document will be updated
* You can get aggregated results back straight from couch with a simple
`MyIndicators.get_result('visits_week', key=[domain, owner_id])`, which will be correct
for the current date/time with no real-time computation, and will return the
data in the following format:

    ```json
    {
        "all_visits": 26,
        "bp_visits": 15,
        "bp_max": 140
    }
    ```

## Emitting custom values
Yield a list where the second value in the list is the value you want to be emitted.

This is useful if you want to do more than just count events. Options for aggregation are:
  * count
  * sum
  * max
  * min
  * sumsqr


In the example above the `temp_max` emitter emits `action.temperature` for each action.
It also specifies that the final value should be the `max` of all the emitted values in the date range.


