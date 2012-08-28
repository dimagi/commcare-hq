pillowtop
=========

A couchdb listening framework to transform and process changes.

Config a json file

logstash

elasticsearch

couchdb url
filter (optional)
transform functions (required)
function must have signature of:
func(doc_json, db)
where doc_json is the doc that was referenced by the _changes feed, and the db passed is the one used to open the document(in case more needs to be done)

the function must return a json dictionary for it to be sent off to the endpoint
