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


sudo apt-get install s3cmd
mv .travis/s3cfg ~/.s3cfg
echo "access_key = $ARTIFACTS_AWS_ACCESS_KEY_ID" >> ~/.s3cfg
echo "secret_key = $ARTIFACTS_AWS_SECRET_ACCESS_KEY" >> ~/.s3cfg

mkdir ~/wheelhouse
s3cmd sync s3://wheelhouse.dimagi.com/python26/ ~/wheelhouse

pip install --upgrade https://bitbucket.org/pypa/setuptools/downloads/setuptools-0.8b3.tar.gz
pip install -e git+https://github.com/pypa/pip#egg=pip
pip install wheel --use-mirrors

bash -ex install.sh