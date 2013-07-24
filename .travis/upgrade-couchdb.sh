curl http://127.0.0.1:5984/
sudo add-apt-repository -y ppa:nilya/couchdb-1.3
sudo apt-get update
sudo apt-get install -qq -y couchdb
sudo service couchdb restart 
sleep 3
curl http://127.0.0.1:5984/
