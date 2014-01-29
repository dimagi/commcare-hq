#!/bin/bash

# Install script for CommCare HQ on Ubuntu 12.04
# - installs all dependencies
# - ensures all necessary processes will run on startup
# - creates databases 
#
# Before running, you must download the JDK 7 tar.gz from
# http://www.oracle.com/technetwork/java/javase/downloads/index.html and save
# it as jdk.tar.gz in the same directory as this script.


# Database settings; change these if desired

POSTGRES_DB="foodb"
POSTGRES_USER="django"
POSTGRES_PW="django"

COUCHDB_DB="foodb"

## Misc settings

ES_VERSION=0.20.5
MINIMAL_INSTALL=
JDK=1

if [ ! -f jdk.tar.gz ]; then
    echo "WARNING: No JDK tarball found; some pieces of CommCareHQ (Cloudcare) may be nonfunctional"
    JDK=
    MINIMAL_INSTALL=1
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

    cat requirements/apt-package.txt | sed 's/#.*$//g' | xargs sudo apt-get install -y

else
    command -v yum > /dev/null 2>&1
    if [ $? -eq 0 ]; then
    # undent
    PM=yum-rhel
    
    sudo rpm -Uvh http://www.gtlib.gatech.edu/pub/fedora-epel/6/x86_64/epel-release-6-7.noarch.rpm
    sudo yum update
    sudo yum clean all

    cat requirements/yum-packages.txt | sed 's/#.*$//g' | xargs sudo yum install -y

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
# 3.0b1 has a bug that affects our fabfile
sudo pip install virtualenv virtualenvwrapper supervisor==3.0a10
echo_supervisord_conf | sudo tee /etc/supervisord.conf

curl -L https://gist.github.com/raw/1213031/929e578faae2ad3bcb29b03d116bcb09e1932221/supervisord.conf | sudo tee /etc/init/supervisord.conf && sudo start supervisord


if [[ ! $(grep virtualenvwrapper ~/.bashrc) ]]; then
    echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
    source ~/.bashrc
fi

## Install Java ##
if [ "$JDK" ] && [ ! -d /usr/lib/jvm/jdk1.7.0 ]; then
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
if [ "$JDK" ] && [ ! -d /usr/local/lib/jython ]; then
    if [ ! -f jython_installer-2.5.2.jar ]; then
        wget http://downloads.sourceforge.net/project/jython/jython/2.5.2/jython_installer-2.5.2.jar
    fi

    # Set /usr/local/lib/jython as the target directory
    sudo java -jar jython_installer-2.5.2.jar --silent -d /usr/local/lib/jython

    sudo ln -s /usr/local/lib/jython/bin/jython /usr/local/bin/

    if [ ! -f ez_setup.py ]; then
        wget http://peak.telecommunity.com/dist/ez_setup.py
    fi

    sudo jython ez_setup.py
fi

## Install couchdb ##
# from http://onabai.wordpress.com/2012/05/10/installing-couchdb-1-2-in-ubuntu-12-04/
if [ ! -f /etc/init.d/couchdb ]; then
    if [ ! -f apache-couchdb-1.2.1.tar.gz ]; then
        wget http://mirrors.ibiblio.org/apache/couchdb/source/1.3.1/apache-couchdb-1.3.1.tar.gz
    fi

    tar xzf apache-couchdb-1.3.1.tar.gz
    cd apache-couchdb-1.3.1
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
    cd .. && rm -r apache-couchdb-1.3.1

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
if [ ! "$MINIMAL_INSTALL" ] && ! -f /etc/init.d/couchdb-lucene ]; then
    if [ ! -f v0.8.0.zip ]; then
        wget https://github.com/rnewson/couchdb-lucene/archive/v0.8.0.zip
    fi

    unzip v0.8.0.zip
    sudo mv couchdb-lucene-0.8.0 /usr/local
    sudo cp /usr/local/couchdb-lucene-0.8.0/tools/etc/init.d/couchdb-lucene/couchdb-lucene /etc/init.d/
fi

if [ -e /usr/local/etc/couchdb/local.ini ] && [[ ! $(grep _fti /usr/local/etc/couchdb/local.ini) ]]; then
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
if [ "$JDK" ] && [ ! -f /etc/init.d/elasticsearch ]; then
    if [ "$PM" = "apt-ubuntu" ]; then
        file=elasticsearch-$ES_VERSION.deb
        if [ ! -f $file ]; then
            wget https://download.elasticsearch.org/elasticsearch/elasticsearch/$file
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

if [ ! "$MINIMAL_INSTALL" ]; then
    sudo update-alternatives --install "/usr/bin/java" "java" "/usr/lib/jvm/jdk1.7.0/bin/java" 1
    sudo update-alternatives --install "/usr/bin/javac" "javac" "/usr/lib/jvm/jdk1.7.0/bin/javac" 1
    sudo update-alternatives --install "/usr/bin/javaws" "javaws" "/usr/lib/jvm/jdk1.7.0/bin/javaws" 1
fi

sudo update-alternatives --config java

## Ensure services start on startup ##
if [ ! "$MINIMAL_INSTALL" ]; then
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
fi

## Configure databases ##
DB=$POSTGRES_DB
USER=$POSTGRES_USER
PW=$POSTGRES_PW
sudo -u postgres createdb $DB
echo "CREATE USER $USER WITH PASSWORD '$PW'; ALTER USER $USER CREATEDB;" | sudo -u postgres psql $DB

curl -X PUT "http://localhost:5984/$COUCHDB_DB"

