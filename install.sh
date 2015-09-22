#!/bin/bash

# Install script for CommCare HQ on Ubuntu 12.04
# - installs all dependencies
# - ensures all necessary processes will run on startup
# - creates databases 
#
# Assumptions when running this install script:
# - You have downloaded Git (sudo apt-get install git) and cloned this repository (git clone URL_OF_THIS_REPOSITORY)
#   because it references the requirements folder


# Database settings
# (`: ${FOO=bar}` is bash's "set if not set" notation)
: ${POSTGRES_DB="commcarehq"}
: ${POSTGRES_REPORTING_DB="commcarehq_reporting"}
: ${POSTGRES_USER="commcarehq"}
: ${POSTGRES_PW="commcarehq"}

: ${COUCHDB_DB="commcarehq"}
: ${COUCHDB_USER="commcarehq"}
: ${COUCHDB_PW="commcarehq"}

## Misc settings

ES_VERSION=0.90.13

#We have to get the latest apt-packages.txt file from the dimagi site
if [ ! -d requirements  ]; then
    echo "Requirements haven't yet been downloaded"
    mkdir requirements && cd requirements
    wget https://raw.github.com/dimagi/commcare-hq/master/requirements/apt-packages.txt
    cd ..
fi

## Install OS-level package dependencies
command -v apt-get > /dev/null 2>&1
if [ $? -eq 0 ]; then
    PM=apt-ubuntu

    # ## PPA to get latest versions of nodejs and npm
    # if [[ ! $(sudo grep -r "chris-lea/node\.js" /etc/apt/) ]]; then
    
    #    # Checks if add-apt-repository is available
    #    # add-apt-repository is provided by the software-properties-common package
    #    if [[ ! $(command -v add-apt-repository) ]]; then
    #        sudo apt-get -y install software-properties-common
    #    fi

    #    sudo add-apt-repository -y ppa:chris-lea/node.js
    # fi
    curl -sL https://deb.nodesource.com/setup_0.10 | sudo -E bash -
    sudo apt-get update
    sudo apt-get install -y nodejs

    ## Ignore packages that have the [travis_ignore] hashtag from the apt-packages.txt file if TRAVIS_INSTALL = yes
    if [ "$TRAVIS_INSTALL" == "y" ]; then
        grep -v '\[travis_ignore\]' requirements/apt-packages.txt | sed 's/#.*$//g' | xargs sudo apt-get install -y
    else
        cat requirements/apt-packages.txt | sed 's/#.*$//g' | xargs sudo apt-get install -y
    fi

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
if [ ! -d /usr/lib/jvm/jdk1.7.0 ]; then
    if [ ! -f jdk.tar.gz ]; then
        # See http://stackoverflow.com/questions/10268583/how-to-automate-download-and-installation-of-java-jdk-on-linux
        wget -O jdk.tar.gz --no-check-certificate --no-cookies --header "Cookie: oraclelicense=accept-securebackup-cookie" http://download.oracle.com/otn-pub/java/jdk/7u67-b01/jdk-7u67-linux-x64.tar.gz
    fi
    tar -xzf jdk.tar.gz
    sudo mkdir -p /usr/lib/jvm
    sudo mv ./jdk1.7.0* /usr/lib/jvm/jdk1.7.0

    sudo update-alternatives --install "/usr/bin/java" "java" "/usr/lib/jvm/jdk1.7.0/bin/java" 1
    sudo update-alternatives --install "/usr/bin/javac" "javac" "/usr/lib/jvm/jdk1.7.0/bin/javac" 1
    sudo update-alternatives --install "/usr/bin/javaws" "javaws" "/usr/lib/jvm/jdk1.7.0/bin/javaws" 1

    sudo update-alternatives --auto java
fi

## Install Jython ##
if [ ! -d /usr/local/lib/jython ]; then
    if [ ! -f jython_installer-2.5.2.jar ]; then
        wget http://downloads.sourceforge.net/project/jython/jython/2.5.2/jython_installer-2.5.2.jar
    fi

    # Set /usr/local/lib/jython as the target directory
    echo "Make sure to enter  /usr/local/lib/jython as the Target Directory"
    sudo java -jar jython_installer-2.5.2.jar -d /usr/local/lib/jython

    sudo ln -s /usr/local/lib/jython/bin/jython /usr/local/bin/

    if [ ! -f ez_setup.py ]; then
        wget http://peak.telecommunity.com/dist/ez_setup.py
    fi

    sudo jython ez_setup.py
fi

## Install couchdb ##
# from http://onabai.wordpress.com/2012/05/10/installing-couchdb-1-2-in-ubuntu-12-04/
if [ ! -f /etc/init.d/couchdb ]; then
    
    if [ "$PM" = "apt-ubuntu" ]; then
        #In ubunt, we use the nilya/couchdb-1.3 as done on the travis build
        sudo add-apt-repository -y ppa:nilya/couchdb-1.3
        sudo apt-get update
        sudo apt-get install -y couchdb
    elif  [ "$PM" = "yum-rhel" ]; then
    #We have to download the file and make it if we're using yum
    if [ ! -f apache-couchdb-1.2.1.tar.gz ]; then
        wget http://pkgs.fedoraproject.org/repo/pkgs/couchdb/apache-couchdb-1.3.1.tar.gz/2ff71e7c55634bb52eca293368183b40/apache-couchdb-1.3.1.tar.gz
    fi

    tar xzf apache-couchdb-1.3.1.tar.gz
    cd apache-couchdb-1.3.1
        sudo mkdir -p /usr/local/var/log/couchdb \
            /usr/local/var/lib/couchdb \
            /usr/local/var/run/couchdb

        # this is not actually for all yum installs, just 64-bit
        ./configure --prefix=/usr/local --enable-js-trunk --with-erlang=/usr/lib64/erlang/usr/include
        make 
        sudo make install
        cd .. && rm -r apache-couchdb-1.3.1
    fi

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
    sudo chown -R couchdb:couchdb /usr/local/etc/couchdb
fi

## Install elastic-search ##
if [ ! -f /etc/init.d/elasticsearch ]; then
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

sudo update-alternatives --install "/usr/bin/java" "java" "/usr/lib/jvm/jdk1.7.0/bin/java" 1
sudo update-alternatives --install "/usr/bin/javac" "javac" "/usr/lib/jvm/jdk1.7.0/bin/javac" 1
sudo update-alternatives --install "/usr/bin/javaws" "javaws" "/usr/lib/jvm/jdk1.7.0/bin/javaws" 1


sudo update-alternatives --auto java

## Ensure services start on startup ##
if [ "$PM" = "apt-ubuntu" ]; then
    sudo update-rc.d couchdb defaults

    # these should already be on by default
    sudo update-rc.d elasticsearch defaults
    sudo update-rc.d postgresql defaults
elif [ "$PM" = "yum-rhel" ]; then
    sudo chkconfig --add couchdb
    sudo chkconfig --add elasticsearch
    sudo chkconfig --add postgresql

    sudo chkconfig couchdb on
    sudo chkconfig elasticsearch on
    sudo chkconfig postgresql on
fi

## Ensure services are running ##
sudo service couchdb start
sudo service elasticsearch start
sudo service postgresql start

## Configure databases ##
DB=$POSTGRES_DB
REPORTING_DB=$POSTGRES_REPORTING_DB
USER=$POSTGRES_USER
PW=$POSTGRES_PW

sudo -u postgres createdb $DB
sudo -u postgres createdb $REPORTING_DB
echo "CREATE USER $USER WITH PASSWORD '$PW'; ALTER USER $USER CREATEDB;" | sudo -u postgres psql $DB

curl -X PUT "http://localhost:5984/$COUCHDB_DB"
if [[ -n $COUCHDB_USER ]]; then
    curl -X PUT "http://localhost:5984/_config/admins/$COUCHDB_USER" -d \"$COUCHDB_PW\"
fi
