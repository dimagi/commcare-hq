LOG=install.log

set -ex

keytool -genkey \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000 \
  -alias javarosakey \
  -keypass onetwothreefourfive \
  -keystore InsecureTestingKeyStore \
  -storepass onetwothreefourfive \
  -dname 'CN=Foo, OU=Bar, O=Bizzle, L=Bazzle, ST=Bingle, C=US'

bash -ex install.sh

apt-get install s3cmd
mv s3cfg ~/.s3cfg
echo "access_key = $ARTIFACTS_AWS_ACCESS_KEY_ID" >> ~/.s3cfg
echo "secret_key = $ARTIFACTS_AWS_SECRET_ACCESS_KEY" >> ~/.s3cfg

mkdir ~/wheelhouse
s3cmd sync s3://wheelhouse.dimagi.com ~/wheelhouse