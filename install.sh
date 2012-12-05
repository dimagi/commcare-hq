# Change these if desired
POSTGRES_DB="foodb"
POSTGRES_USER="django"
POSTGRES_PW="django"

COUCHDB_DB="foodb"

# This script installs dependencies for CommCare HQ on Ubuntu 12.04 (Java,
# Jython, couchdb, couchdb-lucene, less, uglifyjs, and various python packages)
# and sets couchdb and couchdb-lucene up to automatically run on startup.  It
# also creates postgres (user 'django', pass 'django') and couchdb databases
# named according to $DBNAME as specified above. 

# Before running, you must download the following files to the script's
# directory: 
#  - the JDK 7 tar.gz from
#    http://www.oracle.com/technetwork/java/javase/downloads/index.html and
#    save it as jdk.tar.gz
# 
#  - jython_installer-2.5.2.jar from http://jython.org/downloads.html
#
#  - apache-couchdb-1.2.0.tar.gz from http://couchdb.apache.org/#download

if [[ ! $(sudo grep -r "chris-lea/node\.js" /etc/apt/) ]]; then
    sudo add-apt-repository -y ppa:chris-lea/node.js
    sudo apt-get update
fi

if [ ! -f couchdb-lucene-0.8.0-dist.zip ]; then
    wget https://github.com/downloads/rnewson/couchdb-lucene/couchdb-lucene-0.8.0-dist.zip -O couchdb-lucene-0.8.0-dist.zip
fi

## Install dependencies ##

sudo apt-get install nodejs npm
sudo npm install less uglify-js -g

sudo apt-get install -y curl python-pip python-dev libevent-1.4-2 libevent-dev python-setuptools build-essential
sudo apt-get install -y postgresql memcached
sudo apt-get build-dep -y python-psycopg2 python-lxml

sudo pip install --upgrade pip
sudo pip install virtualenv virtualenvwrapper

if [[ ! $(grep virtualenvwrapper ~/.bashrc) ]]; then
    echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
    source ~/.bashrc
fi

## Install Java ##

if [ ! -d /usr/lib/jvm/jdk1.7.0 ]; then
    tar -xvzf jdk.tar.gz
    sudo mkdir /usr/lib/jvm
    sudo rm -r /usr/lib/jvm/jdk1.7.0/
    sudo mv ./jdk1.7.0* /usr/lib/jvm/jdk1.7.0

    sudo update-alternatives --install "/usr/bin/java" "java" "/usr/lib/jvm/jdk1.7.0/bin/java" 1
    sudo update-alternatives --install "/usr/bin/javac" "javac" "/usr/lib/jvm/jdk1.7.0/bin/javac" 1
    sudo update-alternatives --install "/usr/bin/javaws" "javaws" "/usr/lib/jvm/jdk1.7.0/bin/javaws" 1

    sudo update-alternatives --config java
fi

## Install Jython ##

if [ ! -d /usr/local/lib/jython ]; then
    # Set /usr/local/lib/jython as the target directory
    sudo java -jar jython_installer-2.5.2.jar

    sudo ln -s /usr/local/lib/jython/bin/jython /usr/local/bin/

    wget http://peak.telecommunity.com/dist/ez_setup.py

    sudo jython ez_setup.py

    /usr/local/lib/jython/bin/easy_install django
    /usr/local/lib/jython/bin/easy_install django-jython
fi

## Install couchdb ##
# from http://onabai.wordpress.com/2012/05/10/installing-couchdb-1-2-in-ubuntu-12-04/

if [ ! -f /etc/init.d/couchdb ]; then
    sudo apt-get install g++
    sudo apt-get install erlang-base erlang-dev erlang-eunit erlang-nox
    sudo apt-get install libmozjs185-dev libicu-dev libcurl4-gnutls-dev libtool

    tar xvzf apache-couchdb-1.2.0.tar.gz
    cd apache-couchdb-1.2.0

    ./configure
    make 
    sudo make install

    cd .. && rm -r apache-couchdb-1.2.0

    sudo adduser --disabled-login --disabled-password --no-create-home couchdb
    sudo chown -R couchdb:couchdb /usr/local/var/log/couchdb
    sudo chown -R couchdb:couchdb /usr/local/var/lib/couchdb
    sudo chown -R couchdb:couchdb /usr/local/var/run/couchdb

    sudo ln -s /usr/local/etc/init.d/couchdb /etc/init.d

    sudo update-rc.d couchdb defaults
fi


## Install couchdb-lucene ##

if [ ! -f /etc/init.d/couchdb-lucene ]; then
    unzip couchdb-lucene-0.8.0-dist.zip
    sudo cp couchdb-lucene-0.8.0 /usr/local
    rm -r couchdb-lucene-0.8.0
    sudo cp /usr/local/couchdb-lucene-0.8.0/tools/etc/init.d/couchdb-lucene/couchdb-lucene /etc/init.d/


    sudo update-rc.d couchdb-lucene defaults
fi

if [[ ! $(grep _fti /usr/local/etc/couchdb/local.ini) ]]; then
    config=/usr/local/etc/couchdb/local.ini
    sudo sed -i '/\[couchdb\]/ a\os_process_timeout=60000' $config

    echo "
[external]
fti=/usr/bin/python /usr/local/couchdb-lucene-0.8.0/tools/couchdb-external-hook.py

[httpd_db_handlers]
_fti = {couch_httpd_external, handle_external_req, <<\"fti\">>}
" | sudo tee -a $config

fi

## Configure databases ##

DB=$POSTGRES_DB
USER=$POSTGRES_USER
PW=$POSTGRES_PW

sudo -u postgres createdb $DB
echo "CREATE USER $USER WITH PASSWORD '$PW'; ALTER USER $USER CREATEDB;" | sudo -u postgres psql $DB

curl -X PUT "http://localhost:5984/$COUCHDB_DB"

