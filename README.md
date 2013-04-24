Fluff is a library that works with pillowtop and couchdbkit and
lets you define a set of computations to do
on all docs of a doc_type, i.e. perform a map over them, and then use
couchdb to aggregate over the output.

The advantages of this over a normal map reduce are that you get to write
your map in python with full access to the database.

This document describes the intended capabilities;
what's currently here is very preliminary.

Example:

```python

import fluff

class VisitCalculator(fluff.Calculator):
    @fluff.emitter
    def all_visits(self, case):
        for action in case.actions:
            yield action.date

    def bp_visits(self, case):
        for action in case.actions:
            if is_bp(case):
                yield action.date


class MyIndicators(fluff.IndicatorDocument):
    document_class = CommCareCase
    visits_week = VisitCalculator(window=timedelta(days=7))
    visits_month = VisitCalculator(window=timedelta(days=30))

    @classmethod
    def key(self, case):
        return [case.case.owner_id]

# add this pillow to settings.PILLOWTOPS
MyIndicatorsPillow = MyIndicators.pillow()

```

By creating a simple setup of this sort, you'll get a bunch of stuff for free:

* Whenever a doc changes, the corresponding indicator document will be updated
* You can get aggregated results back straight from couch with a simple
`MyIndicators.get_result('visits_week', key=[owner_id])`, which will be correct
for the current date/time with no real-time computation