import argparse
import getpass
import sys

from requests.exceptions import HTTPError

from utils import (
    do_couch_request,
    check_connection,
    confirm,
    do_node_local_request,
    NodeDetails
)


def _copy_db_doc(from_details, to_details, db_name):
    try:
        do_node_local_request(to_details[0], '_dbs/{}'.format(db_name))
    except HTTPError as e:
        if e.response.status_code != 404:
            raise
    else:
        print("{} already exists in destination cluster".format(db_name))
        return

    from_db_doc = do_node_local_request(from_details, '_dbs/{}'.format(db_name))
    to_db_doc = {
        '_id': from_db_doc['_id'],
        'shard_suffix': from_db_doc['shard_suffix'],
        'changelog': [],
        'by_node': {},
        'by_range': {}
    }

    db_shards = None
    for node_name, shards in from_db_doc['by_node'].items():
        if from_details.ip in node_name:
            db_shards = shards
            break

    if not db_shards:
        print('Unable to find shards for db {}'.format(db_name))
        return

    for detail in to_details:
        to_db_doc['by_node']['couchdb@{}'.format(detail.ip)] = db_shards

    nodes = ['couchdb@{}'.format(detail.ip) for detail in to_details]
    for shard in db_shards:
        to_db_doc['by_range'][shard] = nodes

    print('  Updating db config for {}'.format(db_name))
    do_node_local_request(to_details[0], '_dbs/{}'.format(db_name), method='put', json=to_db_doc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Copy a database from one cluster to another')
    parser.add_argument('--from-cluster-ip', dest='from_ip', required=True,
                        help='IP of node in "from" cluster')
    parser.add_argument('--to-cluster-nodes', dest='to_nodes', required=True, nargs='+',
                        help='IP of nodes in "to" cluster that database shards are on.')
    parser.add_argument('--from-username', dest='from_username', required=True,
                        help='Admin username for "from" cluster')
    parser.add_argument('--to-username', dest='to_username',
                        help='Admin username for "to" cluster (defaults to the same as "from-username"')
    parser.add_argument('--database', dest='database', help='Database to copy or "ALL"')
    args = parser.parse_args()

    print args.to_nodes

    from_password = getpass.getpass('Password for "{}@{}"'.format(args.from_username, args.from_ip))
    from_details = NodeDetails(args.from_ip, 15984, 15986, args.from_username, from_password)
    check_connection(from_details)

    to_username = args.to_username or args.from_username
    to_password = getpass.getpass('Password for "{}@{}"'.format(to_username, args.to_nodes[0]))
    to_details = [
        NodeDetails(node_ip, 15984, 15986, to_username, to_password)
        for node_ip in args.to_nodes
    ]
    for details in to_details:
        check_connection(to_details[0])

    if not confirm("Have you copied the shard files from {} to {}?".format(args.from_ip, args.to_nodes)):
        line = "=" * 40
        print(line)
        print("Copy the shard files to the new node before updating couchdb2 with new node config.")
        print(line)
        sys.exit(1)

    if args.database == 'ALL':
        dbs = do_couch_request(from_details, '_all_dbs')
    else:
        dbs = [args.database]
    print(dbs)
    for db_name in dbs:
        if db_name.startswith('_'):
            print('Skipping {}'.format(db_name))
            continue
        _copy_db_doc(from_details, to_details, db_name)
