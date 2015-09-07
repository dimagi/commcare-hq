pillowtop
=========
[![Build Status](https://travis-ci.org/dimagi/pillowtop.png)](https://travis-ci.org/dimagi/pillowtop)
[![Test coverage](https://coveralls.io/repos/dimagi/pillowtop/badge.png?branch=master)](https://coveralls.io/r/dimagi/pillowtop)
[![PyPi version](https://pypip.in/v/pillowtop/badge.png)](https://pypi.python.org/pypi/pillowtop)
[![PyPi downloads](https://pypip.in/d/pillowtop/badge.png)](https://pypi.python.org/pypi/pillowtop)

A couchdb listening framework to transform and process changes.

Django Config
=============

In your settings file, add a  PILLOWTOPS = [] array

Fill the array with the fully qualified class names of your pillows, for example:

    'corehq.pillows.CasePillow',
    'corehq.pillows.AuditcarePillow',
    'corehq.pillows.CouchlogPillow',
    'corehq.pillows.DevicelogPillow',

The pillows depending on their config, need the following:

- A couch db to connect to its _changes feed
- An optional _changes filter

Supported backends:

- Network Listener

  Currently this lets you arbitrarily send your changes results to a TCP socket. This is for the
  logstash log consumption system.

- Elastic Listener

  For elasticsearch endpoint to send json data directly to an elasticsearch index+type mapping.


Running pillowtop
=================

    python manage.py run_ptop --all

This will fire off 1 gevent worker per pillow in your PILLOWTOPS array listening continuously on
the changes feed of their interest.

This process does not pool right now the changes listeners, so be careful,
or suggest an improvement :)

You can also run this for only a single pillow in your PILLOWTOPS array with:

    python manage.py run_ptop --pillow-key=KEY

Pillowtop also will keep checkpoints in couch so as to not keep going over changes when the
process is restarted - all BasicPillows will keep a document unique to its class name in the DB
to keep its checkpoint based upon the _seq of the changes listener it is on.


Understanding pillowtop
=======================

At its core, pillowtop can be thought of as executing the following pseudo-code:

    for line in get_changes_forever():
        if filter(line):
            intermediate_1 = change_trigger(line)
            intermediate_2 = change_transform(intermediate_1)
            change_transport(intermediate_2)

Conceptually, it may be easier to think of if you think of pillowtop as an ETL tool.
Doing that the methods roughly map as follows (using the common examples in our stack):

```
change_trigger --> extract --> get document from couch
change_transform --> transform --> reformat document (this is often a no-op)
change_transport --> load --> save document somewhere else (usually elastic search or postgres)
```

The various subclasses of pillows override various parts of these depending on what they are trying to do.
Two important ones are `AliasedElasticPillow` and `PythonPillow`.

AliasedElasticPillow
--------------------

`AliasedElasticPillow` conceptually maps the following functions:

```
change_trigger --> if the document is being deleted, delete it in elasticsearch as well. otherwise return it from couch.
change_transform --> do some fancy stuff with indices and then save to elastic
```

All of the rest of the complicated logic inside it is related to index management and the process of saving to elastic.
It would be nice if these were more encapsulated.


PythonPillow
------------

PythonPillow conceptually doesn't touch any of the ETL functions.
Instead it just provides a wrapper around around the processing, such that instead of relying on couch-based filters on the changes feed, it uses python filters.
It also adds the ability to process documents in chunks.

It would be nice if you could use PythonPillow as more of a mixin instead of subclassing it, but this is not possible today.


Extending pillowtop
===================

Inherit the BasicPillow class

Implement at a bare minimum change_transport - and override the other processing steps where
necessary.
