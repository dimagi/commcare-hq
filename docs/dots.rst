DOTS on PACT
============

Directly Observe Treatment Short Course is the method in which PACT administers their medication to their patients.

The CHW will observe their patient taking their meds and/or check their pillbox or get verbal assent
on their adherence.

In our application, there's a custom mobile widget in CommCare that shows the dots entry.

It lets you enter drugs taken for both their Non-ART and ART meds.
Each drug class has its own regimen (once a day, twice, thrice, etc) a day.

These properties are stored on the patient's case as

non_art_regimen = int (0-4)
art_regimen = int (0-4)

if you have any of these regimens set not None is:

Non art regimen day slot:
dot_n_one
dot_n_two
dot_n_three
dot_n_four

art regimen day slots
dot_a_one
dot_a_two
dot_a_three
dot_a_four

these are integers 1,2,3,4 (morning, noon, afternoon bedtime)
if there is no regimen for that slot, then they are None.

So for example, say a patient has non_art_regimen = 2 (BD)
then they could have properties:
dot_n_one = 1
dot_n_two = 2
indicating morning, noon pill times.
the dot_n_three and four will be Null

Likewise art regimen is filled same way.


DOTS Submissions
================

When they are submitted, dots come in as a case property ``dots``
This is an xml fragment whos contents are a json dictionary. Yes, that happened.

With the submission in, there's a signal that pact triggers that evals the dots blob into json
and stores it again in the xform under ``pact_dots_data_`` property of the xform.

DOTS Structure
==============

| {
|    "dots": {
|        "regimen_labels": [
|            [0,1,3],
|            [0,3]
|         ],
|         "regimens": [3,2],
|      "days": [ # see below ],
|      "anchor_date": "14 Aug 2013 04:00:00 GMT"
| }

The actual days structure is a 21 length array of the prior observations ask known by the case.
The last 21 days start from element 0 (anchor_date - 21days) to anchor_date at index -1.

Each element of each day array will look like this:

========== ================================    =====================
           Non-ART                             ART
========== ================================    =====================
Slot 1     state, method, note, slot_label     state, method, note, slot_label
Slot 2     state, method, note, slot_label     state, method, note, slot_label
Slot 3     state, method, note, slot_label
Slot 4


