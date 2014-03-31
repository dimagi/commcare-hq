==========
Fake Data
==========

This module lets you generate fake users, cases, and form submissions for
testing the scalability of HQ.
View and edit ``fake_it.py`` to change the numbers created.
To run, open a django shell and run::

    from scripts.fake_it import make_users
    make_users()

You may need to edit ``manage.py`` to enble the gevent monkey patching by default.
(change ``if "gevent" in sys.argv:`` to ``if True:``)

Notes
=====

This data is very time consuming to create at scale.

To produce the following took about 5 days of continuous operation:

 * 5k CC users with
    * 430 cases, with
        * 3.5 forms each, on average
