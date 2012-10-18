pillowtop
=========

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

A couch db to connect to its _changes feed
An optional _changes filter

Supported backends:
Network Listener
Currently this lets you arbitrarily send your changes results to a TCP socket. This is for the
logstash log consumption system.

Elastic Listener
For elasticsearch endpoint to send json data directly to an elasticsearch index+type mapping.

Extending pillowtop
===================

Inherit the BasicPillow class
Implement at a bare minimum change_transport - and override the other processing steps where
necessary.


Running pillowtop
=================

python manage.py run_ptop

This will fire off 1 gevent worker per pillow in your PILLOWTOPS array listening continuosly on
the changes feed of their interest.

This process does not pool right now the changes listeners, so be careful,
or suggest an improvement :)

Pillowtop also will keep checkpoints in couch so as to not keep going over changes when the
process is restarted - all BasicPillows will keep a document unique to its class name in the DB
to keep its checkpoint based upon the _seq of the changes listener it is on.

