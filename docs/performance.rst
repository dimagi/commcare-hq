Performance
============

Right now this is a work in progress, that I'm using to brainstorm scalability testing.
Eventually I'd like to turn this into documentation about HQ performance


Process:
Make 10k users and 1M cases
Try stuff out
write down pain points

Tools
-----
Generate Fake Data
~~~~~~~~~~~~~~~~~~~
domains
user data
cases (via mock form submissions?)

Simulate Production Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
sandbox!

Metrics
-------

Issues
------



1 Domain
1000 web users
10000 cc users
1,000,000 cases
10,000,000 xforms (optional)

Use explode_cases

new Postgres_db (server setup confluence setup).
new couchdb
Vagrant VM
spoof form submission times: https://github.com/dimagi/hq-pact/blob/master/pact/management/commands/__init__.py#L80
https://github.com/dimagi/hq-pact/blob/master/pact/management/commands/utils.py


