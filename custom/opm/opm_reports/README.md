TODO:
in incentive.py, figure out last_month_total
Cron job to finalize reports at the end of each month.  (when, exactly?)

### Extracting data from the db:

from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db

domain_id = db.view('domain/domains', key="opm", reduce=False).one()['id']
cases = CommCareCase.get_all_cases('opm') # json
cases = CommCareCase.get_all_cases('opm', include_docs=True) # python
users = CommCareUser.by_domain('opm') # python
forms = []
for c in cases:
    forms += c.get_forms() # python
