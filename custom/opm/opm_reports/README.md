TODO:
Add all fixture amts to beneficiary report
Cron job to finalize reports at the end of each month.  (when, exactly?)
Show only data from the current report period

    from corehq.apps.fixtures.models import FixtureDataItem
    fixtures = [f.to_json().get('fields') for f in FixtureDataItem.by_domain('opm').all()]
    prices = dict([f.values() for f in fixtures])

Fluff window only lets you specify a timedelta. Fix that ish!

### Running tests and getting fixtures
I had been getting forms from USERS of a domain, but I should have done it from each case!


### Extracting data from the db:

from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db

domain_id = db.view('domain/domains', key="opm", reduce=False).one()['id']
cases = CommCareCase.get_all_cases('opm') # json
users = CommCareUser.by_domain('opm') # python
forms = []
for u in users:
    forms += u.get_forms().all() # python

# formfile = open('opm_forms.json', 'w')
# userfile = open('opm_users.json', 'w')
# casefile = open('opm_cases.json', 'w')

# formfile.write(json.dumps([form.to_json() for form in forms], indent=2))
# userfile.write(json.dumps([u.to_json() for u in users], indent=2))
# casefile.write(json.dumps(cases, indent=2))

with open('opm_test_data.json', 'w') as f:
    f.write(json.dumps([form.to_json() for form in forms], indent=2))
    f.write(json.dumps([u.to_json() for u in users], indent=2))
    f.write(json.dumps(cases, indent=2))




### Setting up test data:
Check out commcare-hq/testrunner.py
capabilities:
if no test_fixtures.json found, generate it from database
load test_fixtures.json to a new database and edit it
overwrite test_fixtures.json from database

# write database to test_fixtures
python test_data.py write db_name [fixtures.json]

# load test_fixtures to empty database:
python test_data.py read [db_name] [fixtures.json]
