Pennsylvania State University
==============================

Custom Reports for the Legacy Together Project


Overview
---------

General
~~~~~~~~
This report measures use of GBG Strategies and Games on a per-week basis.
The report comes in two parts, *Site* and *Individual*.
The *Site* report will display aggregate results for a project site, represented as a user group.
The *Individual* report will show the performance of a particular user.

Technical
~~~~~~~~~~
There will be a celery task run every Saturday at <TBD> that aggregates the data for the reports.
This is saved in a series of docs, one per site.
This doc definition can be seen in `models.py`_  but basically,
it stores weekly totals for the site, as well as results for each user in that site.

Once the reports have been stored, an email is sent out to each user with a link to their individual report.
The user clicks on the report, is redirected to a login page, then sent to the report.




TBD:
    * When do we run the celery task?
    * Does each user get a unique url?  How are urls configured?
        # unique URL per user per week
        # unique URL per user showing latest
        # general URL showing latest for current user
        # Index of available reports for a given user (and unique URLs)
    * Display Individual's username in report?
    * Display some results in email?


week_end_date = datetime.date(2013, 9, 28)
site_strategy = [3, -1, 0, 4, 2]
site_game = [2, 4, 3, 1, 0]
individual = {
    'ethan': {
        'strategy': [2, 4, 0, 1, 3],
        'game': [1, 2, 4, 1, 0],
    }
}

r = LegacyWeeklyReport(domain='mikesproject', site='central')
id:
0c90e7b7110f2451ec225dad783e2cba