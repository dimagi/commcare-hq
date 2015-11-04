#!/bin/bash
set -ev

keytool -genkey \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000 \
  -alias javarosakey \
  -keypass onetwothreefourfive \
  -keystore InsecureTestingKeyStore \
  -storepass onetwothreefourfive \
  -dname 'CN=Foo, OU=Bar, O=Bizzle, L=Bazzle, ST=Bingle, C=US'


# Something accessed the commcarehq DB. Why? Should only access test_commcarehq but let's get it working w/ tests as-is
psql -c 'create database commcarehq' -U postgres
curl -X PUT localhost:5984/commcarehq
