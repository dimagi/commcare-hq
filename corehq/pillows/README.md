# HQ Pillowtop Infrastructure and Workflow

## About Pillows

Pillows are Couch `_changes` feed listeners. They listen to couch changes and do an operation on them in python, and do something.

Many pillows defined here take a couch (kafka) change, and send it over to elasticsearch to be indexed.
They may be transformed to make querying/indexing easier. What's sent to ES need not be 1:1 with what's from couch.

## HQPillow Elastic Workflow

Expect the following structure and components.

 * A mapping in `corehq/pillows/mappings`
    * Mappings are pre-determined structures you send to ES to help type out stuff you want to index.
 * A pillow class generator in `corehq/pillows`
 * A reindexer in the same file
 * Update the `corehq/apps/hqcase/management/commands/ptop_reindexer_v2.py`  management command to register the pillow in the pillowtop preindexing workflow
 * Add your pillow to the main `settings.py`


## Command Reference
 * `ptop_preindex` will call all the registered ptop_fast_reindexers
 * `ptop_es_manage` when called in our deployment workflow (see command flags for reference) - it can flip the index aliases to what's considered master to turn on preindexed indices.
