# Something accessed the commcarehq DB. Why? Should only access test_commcarehq but let's get it working w/ tests as-is
psql -c 'create database commcarehq' -U postgres

# The XFORMS_POST_URL is under suspicion of still pointing at the wrong DB; trying this
curl -X PUT localhost:5984/commcarehq

