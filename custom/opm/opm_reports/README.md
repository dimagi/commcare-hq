## Module structure

* constants.py - useful stuff to be imported wherever
* reports.py - controls the display of the reports.
* beneficiary.py - handles the generation of a row for a specific case
* incentive.py - handles the generation of a row for a specific user/worker
* models.py - stores fluff models for users, cases, and forms
* case_calcs.py/user_calcs.py - houses per-case or per-user Calculators

## Testing

Currently this report has just regression tests.
The normal functionality of the report relies on monthly definitive snapshots.
There is a json file that stores a snapshot, and the data from which it was
generated.
To verify fidelity in reporting, tests recalculate the report based on the
data and check if it matches the snapshot.

## Extracting data from the db:

from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db

domain_id = db.view('domain/domains', key="opm", reduce=False).one()['id']
cases = CommCareCase.get_all_cases('opm') # json
cases = CommCareCase.get_all_cases('opm', include_docs=True) # python
users = CommCareUser.by_domain('opm') # python
forms = []
for c in cases:
    forms += c.get_forms() # python
