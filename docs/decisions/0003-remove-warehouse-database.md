# 3. Remove warehouse database

Date: 2019-10-16

## Status

Accepted

## Context

The data warehouse was intended to house data for all CommCare HQ reports.
The warehouse would replace Elasticsearch in almost all contexts that it is currently used.
The migration began in 2017 with the Application Status report and the effort
to move the report to the warehouse and ensure it is stable, performs well and
provides the same features as the ES-backed reports was much higher than
anticipated.

## Decision

To reduce our infrastructure dependencies and focus our efforts on existing databases,
we have decided to remove the warehouse and stop any efforts to iterate on it.

This decision is not because we believe that the warehouse is a worse implementation than Elasticsearch.
This decision is because we believe that with our current priorities, we will
not be able to spend the appropriate amount of time to make the warehouse a
robust solution for generic reports in the near future.
Because no current reports are backed by the warehouse, it is an important time
to reconsider our approach and decide on what will be appropriate long term.

When there are more dedicated resources for generic reports, we believe that
a warehouse-style approach should be considered when implementing.

## Consequences

The warehouse was intended to reduce our usage of Elasticsearch and assist in
an effort to remove many dependencies on our cluster.
No matter the short term status of the warehouse, we need to improve our
management of ES soon.
This will include upgrading to more recent versions, re-indexing indexes to
contain more shards, and supporting aliases that consist of multiple indexes.

The Application Status report also uniquely adds a lot of load on our CouchDB cluster.
This load comes from the pillows for the report updating the user doc to contain the latest metadata.
There will be a separate change that batches these updates to CouchDB into chunks.
