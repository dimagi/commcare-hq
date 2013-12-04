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

regimen_labels are reiterations of the current state of the case's regimen frequency and the actual
labels set.

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


State can be:
unchecked = not checked by chw at all
empty = pillbox is empty they took their meds
partial = they took only some of their meds (if it's a multi drug dose or something)
full = didn't take their meds

method can be:
direct: chw saw them take their meds - the most trustworthy way.
self: patient reported to chw
pillbox: chw didn't see, but was physically present to inspect pillbox for that day

note is any freetext note for that day. on system generated entries, it'll say so here.

slot_label is the integer label id of what slot this actually is. This is a compatability layer.
it'll match the regimen labels in the top of the dots block in sequence. this is because if
their regimen labels are 3,4 (afternoon, bedtime), it's hard to tell when the integer slot location
in the day json are on the top 2 (due to how we originally wrote it), so we explicitly set
all labels to store the slots on every submission.


DOTS Computation
================

When a dots form comes in, it may or may not have done a pillbox check. However questions in the form
do contain pseudo pillbox check information, so upon submission the server has a signal that detects
a dots submission and rebuilds the dots calculation again.

This is necessary because multiple submissions with multiple "calendar days" will have been submitted
over the course of the day/week/month. The server and the case need to have the "latest" dots calendar
computed with the anchor date of the latest submission.  It reconciles and ensures that direct observations
trump other methods.

For example, if a chw visits monday and sees the pillbox directly for monday the 3rd, but if a chw visits thursday the 6th, the Monday, cell x-3 could
possibly be set as unchecked. The server upon receiving these submissions will reconcile these entries and sure that
direct observations will trump others. See the dots tests to see how the reconciliation works.


Submission workflow
===================

When a dots submission comes in, a signal will see the submission, and rerun the calculation.
The calculation will then create a NEW xform and resubmit with the latest dots information. The signal will ignore these submissions
so as to prevent an infinite loop of submissions.




