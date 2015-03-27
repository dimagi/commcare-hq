read -s -p "Enter Password: " password

while read line
do
    parts=($(echo $line))
    domain=${parts[0]}
    app_id=${parts[1]}
    url="https://www.commcarehq.org/a/$domain/apps/source/$app_id/"
    dir="app_builder_live_test/src/"
    mkdir -p $dir
    curl --digest -u $1:$password $url > $dir/$domain-$app_id.json
done < $2