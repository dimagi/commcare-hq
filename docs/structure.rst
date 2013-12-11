So you wanna do some pact
=========================

This is a custom report that gives EMR-like functionality for CommCareHQ

The core functionality radiates from the reports/ directory

patient_list.py
  a modified case_list using report_case index.
patient.py
  custom report giving emr-like view of a patient.
dot.py
  landing page for the DOT report view
dot_calendar
  actual calendar view
chw_list.py
  a regular tabular report showing all the pact chws and other stats for them
chw.py
  a custom report page that tabs through different views of a patient
chw_schedule
  chw_schedule - logic/display for the "did chw visit patient according to their schedule"
admin_chw_reports, admin_dot_reports, admin_reports
  tabular reports that allow for direct csv downloads


Case Properties of Note
=======================

dot_status
  Whether they're in the DOT monitoring program. When they're DOT, the case properties for dot
  regimens need to be filled in. The options for this is their PACT_DOT_CHOICES for how frequently they'll be visited.

hp_status
  Whether they're in the primary health promotion monitoring program.
  The options for this is their PACT_HP_CHOICES for how frequently they'll be visited.

hp
  This is the actual assigned CHW. All CHWS are part of a case sharing group, but the remote app's ability
  to differentiate actual case assignment happens via this custom property.

pactid
  This is the pact internal identifier.

