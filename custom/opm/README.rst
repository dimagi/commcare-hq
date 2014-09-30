Data
-----
There are three "blocks" of beneficiaries (cases) corresponding to different triggers for incentive payments.
Hard Block -> Atri
Soft Block -> Wazirganj
Control -> ???  (no custom report)

**Differences between Hard and Soft blocks:**
Birth Preparedness 1 -> window_1_3 is called soft_window_1_3
Birth Preparedness 2 -> window_2_3 is called soft_window_2_3
Delivery Form -> no change
Child Followup Form -> same, but look for /data/total_soft_conditions == '1'
Birth Spacing -> no change


Module structure
----------------

-  constants.py - useful stuff to be imported wherever
-  reports.py - controls the display of the reports.
-  beneficiary.py - handles the generation of a row for a specific case
-  incentive.py - handles the generation of a row for a specific
   user/worker
-  models.py - stores fluff models for users, cases, and forms
-  case\_calcs.py/user\_calcs.py - houses per-case or per-user
   Calculators

Extracting data from the db:
----------------------------

::

    from corehq.apps.users.models import CommCareUser, CommCareCase from
    dimagi.utils.couch.database import get_db

    domain_id = db.view('domain/domains', key="opm", reduce=False).one()['id']
    cases = CommCareCase.get_all_cases('opm') # json
    cases = CommCareCase.get_all_cases('opm', include_docs=True) # python
    users = CommCareUser.by_domain('opm') # python
    forms = []
    for c in cases:
        forms += c.get_forms() # python

    # alternatively, this will pull ALL forms from a domain:
    forms = db.view(
        "couchforms/all_submissions_by_domain",
        startkey=['opm'],
        endkey=['opm', {}],
        include_docs=True, reduce=False
    ).all()
