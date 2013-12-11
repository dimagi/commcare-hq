Patient Level Reports
=====================

When in the reports in patient.py, it presents you an EMR like view with multiple tabs

a pact patient is a case.


demographic info
================
It provides a link to cloudcare forms for dot, patient info and bloodwork
there is also a custom form workflow for modifying demographics. This submits a custom made xform to update patient level information in the case.

submissions
===========
Custom list using knockout showing submissions for the given patient. this is elasticsearch backed

schedule
========
Knockout based view of viewing/adding/removing scheduled visits for a given patient.

It's a weekly/daily view of allowing a patient to see  "what chws are supposed to visit me which day of the week"

This is used for how to compute chw visitations.

The schedule is stored in two ways on the patient's case.

the latest schedules are individual case properties by day, with the value being the CHW assigned.
dotScheduleMonday, dotScheduleTuesday,etc.

historical and current schedule is stored as an array in the ``computed_.pact_weekly_schedule`` property.

The array shows time sensitive information (when active from when to when)
The timestamps for the historical schedules are important for computing historical visitations,
in the event that the schedule changes, you want to check historical visits with the schedule
active at the time of the visit.


dots
====

Take a deep breath and head to the dots documentation file


