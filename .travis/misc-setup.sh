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


psql -c 'create database test_commcarehq' -U postgres
curl -X PUT localhost:5984/commcarehq
