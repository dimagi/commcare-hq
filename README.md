Couchforms 
==========

[![Build Status](https://travis-ci.org/dimagi/couchforms.png)](https://travis-ci.org/dimagi/couchforms)
[![Test coverage](https://coveralls.io/repos/dimagi/couchforms/badge.png?branch=master)](https://coveralls.io/r/dimagi/couchforms)
[![PyPi version](https://pypip.in/v/couchforms/badge.png)](https://pypi.python.org/pypi/couchforms)
[![PyPi downloads](https://pypip.in/d/couchforms/badge.png)](https://pypi.python.org/pypi/couchforms)

Put XForms in couchdb!

To run the tests, `pip install -e . && django-admin.py test --settings settings`

To include this in a django project you need the following settings defined in your settings.py

```python
####### Couch Forms & Couch DB Kit Settings #######

COUCH_SERVER_ROOT = 'localhost:5984'
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'database_name'

# you may want to import localsettings here so the variables above can be overridden

def get_server_url(server_root, username, password):
    if username and password:
        return "http://%(user)s:%(pass)s@%(server)s" % \
            {"user": username,
             "pass": password,
             "server": server_root }
    else:
        return "http://%(server)s" % {"server": server_root }
COUCH_SERVER = get_server_url(COUCH_SERVER_ROOT, COUCH_USERNAME, COUCH_PASSWORD)
COUCH_DATABASE = "%(server)s/%(database)s" % {"server": COUCH_SERVER, "database": COUCH_DATABASE_NAME }


COUCHDB_DATABASES = [(app_label, COUCH_DATABASE) for app_label in [
        'couchforms',
    ]
]
```

In order to put up a couchforms url that can receive POSTs, add the following line to urls.py:

```python
#   ...
    (r'desired/url/$',  'couchforms.views.post'),
#   ...
```

In order to test whether this is working, you can send a filled out xform submission (saved at ./sub.xml) for the command line with curl as follows:

```
$ curl -X POST http://localhost:8000/desired/url/ -d @sub.xml
```
