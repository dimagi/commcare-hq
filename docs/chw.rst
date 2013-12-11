PACT CHW Reports
================


The CHW Report view is a management view for CHW Management.

Info Tab
========

Landing page of this report.

Gives basic info on the chw for reference, as well as the patients listed according to the HP field on the patient case.


Submissions Tab
===============

This is a tabular report that's backed by elasticsearch to query the submissions done by this CHW.

Visit Schedule
==============

This is the heart of the report.

It queries all patient cases, gets all their computed visit schedules of chw's that are supposed to visit them.

With all the visit schedules having time bounds of activeness, they are put into an interval tree.
Over the course of the time interval specified in the report, the interval tree is queried
to retrieve the "active" schedule that applies to the date in which you are querying.

With the active schedule retrieved, the day of the week is then checked against that schedule to get the patient ID (pact ID)

The pact ID is then mapped to a case_id.

For each user on that day of week, the CHW's submissions are queried to see if they have a submission for that patient on that day.

If there is no submission, an additional check is one on ALL other chws to see if someone covered for them.

If there is no submission, that is considered a missed visit.

If there is a submission, then the submission ID is noted. Just return the first one you find and consider that a met schedule.

Note, the submission is dated not by the receive date, but by the hand-entered encounter date.


