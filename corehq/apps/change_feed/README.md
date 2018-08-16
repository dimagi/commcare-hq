Changes Feed Application
------------------------

This app provides a [kafka-based](https://kafka.apache.org/) implementation of a changes feed.
This allows for creating an abstraction layer between CouchDB and Pillows so that pillows are not dependent on on the underlying database.
More information about this approach is available on [read the docs](http://commcare-hq.readthedocs.io/change_feeds.html).

# Dependencies

These pillows are dependent on Kafka, which is dependent on Zookeeper.
It is necessary to run these services to provide steady-state synchronization of data to ElasticSearch.
The recommended installation mechanism is via Docker.
See the [HQ docker readme](https://github.com/dimagi/commcare-hq/blob/master/docker/README.md) for more information on doing that.


## Alternative installations

You can also use any of the alternative installation mechanisms if you don't want to or can't use Docker.

### Manually via quickstart

Kafka provides a [quickstart guide](http://kafka.apache.org/documentation.html#quickstart) to getting up and running quickly.


### Natively, on Mac

You can follow the quick start guide above, or you can use brew to install kafka (it installs a slightly older version 0.8).

```
brew install kafka
brew services start zookeeper
brew services start kafka
```

### Via Ansible

You can use Ansible to setup Zookeeper and Kafka on your dev environment, or in a VM.
This can be accomplished using the following script (assuming you have an appropriate ansible environment configured):

```
ansible-playbook -i inventories/development -e '@vars/dev.yml' deploy_stack.yml --tags=kafka
```

# Configuration

If you use the default configuration you should not have to do anything.
If you are running kafka in a VM, on another machine, or on a nonstandard port, you will need to override `KAFKA_BROKERS` in your `localsettings.py`.

To more easily manage Kafka's settings, try installing [kafkat](https://github.com/airbnb/kafkat)

Finally, once you have kafka running, initialize it with

```
./manage.py create_kafka_topics
```
