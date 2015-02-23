Tracking user data: User is a case
==================================

Introduction
------------

This feature allows case properties to be saved/loaded at the
user-level, something we've often thought of as "global app data". Each
user will have one case that represents that user and is assigned to
them. Every form in the app will be able to save/update/reference
properties to/from that user-level case. The basic use case is that a
user will log in and access different modules and forms. However all
data will be tracked at the *user* level, not the case level. Or to put
it another way, the user is also a case.

The Specification_ can be found in Google Docs.


.. _Specification: https://docs.google.com/a/dimagi.com/document/d/1UBNEzuXHbs2yQ3MsKtkuKE5aEoMvu2AnnMTD-pPGKqo/edit?pli=1#heading=h.q3wyha58n4s0


Implementation
--------------

Derek Hans has implemented this concept manually using existing Call
Center functionality for some of his projects, e.g
`mHealth Summit 2014`_. In order not to break existing implementations,
the "Call Center Case Type" field in Basic project settings is
hidden, and the value defaults to "user-case". The value will be looked
up wherever it is used, so that the existing Call Center
user case will be used if it existed prior to the new functionality,
otherwise the new user case will be used.


.. _mHealth Summit 2014: https://www.commcarehq.org/a/mhealth-summit-2014/reports/case_data/83b823cdb68c42b786dc5365f90a8a84/
