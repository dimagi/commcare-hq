sudo add-apt-repository -y ppa:nilya/couchdb-1.3
sudo apt-get update
sudo apt-get install -qq -y couchdb
sudo service couchdb restart
sleep 3