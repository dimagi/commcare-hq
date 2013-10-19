Pennsylvania State University
==============================

Custom Reports for the Legacy Together Project


General Overview
~~~~~~~~~~~~~~~~
This report measures use of GBG Strategies and Games on a per-week basis.
The report comes in two parts, *Site* and *Individual*.
The *Site* report displays aggregate results for a project site, represented as a user group.
The *Individual* report shows the performance of a particular user.


URLs and Permissions
~~~~~~~~~~~~~~~~~~~~
Normal users can view only their own report.
Domain admins can view any user's report.
If you visit the report URL with no parameters, you'll see the latest report for the current user,

**Optional URL params**   
If you specify a username (``user=mike``), you'll see that user's latest report.
If you specify a report id (``r_id=4adcc7ccb6f85617b7a8597c2160fcd9``), you'll see that particular
report for the user as determined before.


Technical
~~~~~~~~~~
There will be a celery task run every Saturday at <TBD> that aggregates the data for the reports.
This is saved in a series of docs, one per site.
This doc definition can be seen in `models.py`_  but basically,
it stores weekly totals for the site, as well as results for each user in that site.

Once the reports have been stored, an email is sent out to each user with a link to their individual report.
The user clicks on the report, is redirected to a login page, then sent to the report.


Next Steps:
    * Email users.
    * Display Individual's username in report?
    * Display some results in email?
    * save dates to be skipped in a once-off doc referred to by ID

Add to total games played everytime the user checks off something about special games
Account for days off
submit a few example forms. (Log in and use cloudcare?)
use psy.py
