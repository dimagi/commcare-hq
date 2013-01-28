#!/bin/bash

# Install script for CommCare HQ on Ubuntu 12.04
# - installs all dependencies
# - ensures all necessary processes will run on startup
# - creates databases 
#
# Before running, you must download the following files to the script's
# directory: 
#  - the JDK 7 tar.gz from
#    http://www.oracle.com/technetwork/java/javase/downloads/index.html and
#    save it as jdk.tar.gz
# 
# When installing Jython, accept the default options and enter
# /usr/local/lib/jython when prompted for the target directory.


# Database settings; change these if desired

POSTGRES_DB="foodb"
POSTGRES_USER="django"
POSTGRES_PW="django"

COUCHDB_DB="foodb"

## Misc settings

ES_VERSION=0.19.12

if [ ! -f jdk.tar.gz ]; then
    echo "Please read the top of this file."
    exit 1
fi

## Install OS-level package dependencies
command -v apt-get > /dev/null 2>&1
if [ $? -eq 0 ]; then
    PM=apt-ubuntu

    sudo apt-get install -y python-software-properties
    ## PPA to get latest versions of nodejs and npm
    if [[ ! $(sudo grep -r "chris-lea/node\.js" /etc/apt/) ]]; then
        sudo add-apt-repository -y ppa:chris-lea/node.js
    fi
    sudo apt-get update

    sudo apt-get install -y git python-pip python-dev libevent-1.4-2 \
        libevent-dev python-setuptools  \
        postgresql memcached \
        nodejs npm \
        gdebi-core

    sudo apt-get build-dep -y python-psycopg2 python-lxml

    # Dependencies for CouchDB and building it
    sudo apt-get install -y g++ curl build-essential \
        erlang-base erlang-dev erlang-eunit erlang-nox \
        libmozjs185-dev libicu-dev libcurl4-gnutls-dev libtool

else
    command -v yum > /dev/null 2>&1
    if [ $? -eq 0 ]; then
    # undent
    PM=yum-rhel
    
    sudo rpm -Uvh http://www.gtlib.gatech.edu/pub/fedora-epel/6/x86_64/epel-release-6-7.noarch.rpm
    sudo yum update
    sudo yum clean all

    sudo yum install -y git gcc gcc-c++ make libtool zlib-devel openssl-devel \
        rubygem-rake ruby-rdoc curl-devel openssl-devel libicu-devel \
        postgresql postgresql-devel postgresql-lib postgresql-server libtool \
        python-devel yum-utils

    # CouchDB
    sudo yum install -y erlang libicu-devel openssl-devel curl-devel make \
        gcc js-devel libtool which

    sudo yum install htop
    sudo yum remove -y mysql php
   
    # get pip executable instead of python-pip
    sudo yum install python-pip
    sudo pip-python install -U pip
else
    command -v brew-todo > /dev/null 2>&1
    if [ $? -eq 0 ]; then
    # undent
    PM=brew
else
    echo "You need either apt or yum to use this script."
    exit 1
fi fi fi

## Install system-wide Python and Node packages
sudo npm install npm
#sudo npm install less uglify-js -g

sudo pip install --upgrade pip
sudo pip install virtualenv virtualenvwrapper supervisor
echo_supervisord_conf | sudo tee /etc/supervisord.conf

if [[ ! $(grep virtualenvwrapper ~/.bashrc) ]]; then
    echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
    source ~/.bashrc
fi

## Install Java ##
if [ ! -d /usr/lib/jvm/jdk1.7.0 ]; then
    tar -xzf jdk.tar.gz
    sudo mkdir /usr/lib/jvm
    sudo rm -r /usr/lib/jvm/jdk1.7.0/
    sudo mv ./jdk1.7.0* /usr/lib/jvm/jdk1.7.0

    sudo update-alternatives --install "/usr/bin/java" "java" "/usr/lib/jvm/jdk1.7.0/bin/java" 
    sudo update-alternatives --install "/usr/bin/javac" "javac" "/usr/lib/jvm/jdk1.7.0/bin/javac" 1
    sudo update-alternatives --install "/usr/bin/javaws" "javaws" "/usr/lib/jvm/jdk1.7.0/bin/javaws" 1

    sudo update-alternatives --config java

fi

## Install Jython ##
if [ ! -d /usr/local/lib/jython ]; then
    if [ ! -f jython_installer-2.5.2.jar ]; then
        wget http://downloads.sourceforge.net/project/jython/jython/2.5.2/jython_installer-2.5.2.jar
    fi

    # Set /usr/local/lib/jython as the target directory
    sudo java -jar jython_installer-2.5.2.jar

    sudo ln -s /usr/local/lib/jython/bin/jython /usr/local/bin/

    if [ ! -f ez_setup.py ]; then
        wget http://peak.telecommunity.com/dist/ez_setup.py
    fi

    sudo jython ez_setup.py
fi

## Install couchdb ##
# from http://onabai.wordpress.com/2012/05/10/installing-couchdb-1-2-in-ubuntu-12-04/
if [ ! -f /etc/init.d/couchdb ]; then
    if [ ! -f apache-couchdb-1.2.0.tar.gz ]; then
        wget http://apache.mirrors.pair.com/couchdb/releases/1.2.0/apache-couchdb-1.2.0.tar.gz
    fi

    tar xzf apache-couchdb-1.2.0.tar.gz
    cd apache-couchdb-1.2.0
    if [ "$PM" = "apt-ubuntu" ]; then
        ./configure
    elif  [ "$PM" = "yum-rhel" ]; then
        sudo mkdir -p /usr/local/var/log/couchdb \
            /usr/local/var/lib/couchdb \
            /usr/local/var/run/couchdb

        # this is not actually for all yum installs, just 64-bit
        ./configure --prefix=/usr/local --enable-js-trunk --with-erlang=/usr/lib64/erlang/usr/include
    fi
    make 
    sudo make install
    cd .. && rm -r apache-couchdb-1.2.0

    if [ "$PM" = "apt-ubuntu" ]; then
        sudo adduser --disabled-login --disabled-password --no-create-home couchdb
        sudo ln -s /usr/local/etc/init.d/couchdb /etc/init.d
    elif [ "$PM" = "yum-rhel" ]; then
        sudo adduser couchdb
        sudo ln -s /usr/local/etc/rc.d/couchdb /etc/init.d
    fi

    sudo chown -R couchdb:couchdb /usr/local/var/log/couchdb
    sudo chown -R couchdb:couchdb /usr/local/var/lib/couchdb
    sudo chown -R couchdb:couchdb /usr/local/var/run/couchdb
fi

## Install couchdb-lucene
if [ ! -f /etc/init.d/couchdb-lucene ]; then
    if [ ! -f couchdb-lucene-0.8.0-dist.zip ]; then
        wget https://github.com/downloads/rnewson/couchdb-lucene/couchdb-lucene-0.8.0-dist.zip
    fi

    unzip couchdb-lucene-0.8.0-dist.zip
    sudo cp couchdb-lucene-0.8.0 /usr/local
    rm -r couchdb-lucene-0.8.0
    sudo cp /usr/local/couchdb-lucene-0.8.0/tools/etc/init.d/couchdb-lucene/couchdb-lucene /etc/init.d/
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

## Install elastic-search ##
if [ ! -f /etc/init.d/elasticsearch ]; then
    if [ "$PM" = "apt-ubuntu" ]; then
        file=elasticsearch-$ES_VERSION.deb
        if [ ! -f $file ]; then
            wget https://github.com/downloads/elasticsearch/elasticsearch/$file
        fi
        sudo gdebi --n $file

        echo "
        JAVA_HOME=/usr/lib/jvm/jdk1.7.0
        " | sudo tee -a /etc/default/elasticsearch

    elif [ "$PM" = "yum-rhel" ]; then
        sudo mkdir /opt
        file=elasticsearch-$ES_VERSION.tar.gz
        if [ ! -f $file ]; then
            wget https://github.com/downloads/elasticsearch/elasticsearch/$file
        fi
        sudo tar -C /opt/ -xzf $file
        sudo ln -s /opt/elasticsearch-$ES_VERSION /opt/elasticsearch

        # install init.d script
        curl -L http://github.com/elasticsearch/elasticsearch-servicewrapper/tarball/master | tar -xz
        mv *servicewrapper*/service /opt/elasticsearch/bin/
        rm -Rf *servicewrapper*
        sudo /opt/elasticsearch/bin/service/elasticsearch install

        echo "
        JAVA_HOME=/usr/lib/jvm/jdk1.7.0
        " | sudo tee /etc/default/elasticsearch
    fi
fi

# We do this again at the end in case anything above (such as gdebi elasticsearch.deb) 
# installs a system java package and changes the configured java install path,
# which we don't want

sudo update-alternatives --install "/usr/bin/java" "java" "/usr/lib/jvm/jdk1.7.0/bin/java" 1
sudo update-alternatives --install "/usr/bin/javac" "javac" "/usr/lib/jvm/jdk1.7.0/bin/javac" 1
sudo update-alternatives --install "/usr/bin/javaws" "javaws" "/usr/lib/jvm/jdk1.7.0/bin/javaws" 1

sudo update-alternatives --config java

## Ensure services start on startup ##
if [ "$PM" = "apt-ubuntu" ]; then
    sudo update-rc.d couchdb defaults
    sudo update-rc.d couchdb-lucene defaults

    # these should already be on by default
    sudo update-rc.d elasticsearch defaults
    sudo update-rc.d memcached defaults
    sudo update-rc.d postgresql defaults
elif [ "$PM" = "yum-rhel" ]; then
    sudo chkconfig --add couchdb
    sudo chkconfig --add elasticsearch
    sudo chkconfig --add memcached
    sudo chkconfig --add postgresql
    sudo chkconfig --add couchdb-lucene

    sudo chkconfig couchdb on
    sudo chkconfig elasticsearch on
    sudo chkconfig memcached on
    sudo chkconfig postgresql on
    sudo chkconfig couchdb-lucene on
fi

## Ensure services are running ##
sudo service couchdb start
sudo service elasticsearch start
sudo service memcached start
sudo service postgresql start

## Configure databases ##
DB=$POSTGRES_DB
USER=$POSTGRES_USER
PW=$POSTGRES_PW
sudo -u postgres createdb $DB
echo "CREATE USER $USER WITH PASSWORD '$PW'; ALTER USER $USER CREATEDB;" | sudo -u postgres psql $DB

curl -X PUT "http://localhost:5984/$COUCHDB_DB"

