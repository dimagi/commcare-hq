# Something accessed the commcarehq DB. Why? Should only access test_commcarehq but let's get it working w/ tests as-is
psql -c 'create database commcarehq' -U postgres
curl -X PUT localhost:5984/commcarehq
