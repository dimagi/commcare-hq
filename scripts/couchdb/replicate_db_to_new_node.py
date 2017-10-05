import sys

from utils import (
    do_couch_request,
    get_arg_parser,
    node_details_from_args,
    check_connection,
    is_node_in_cluster,
    confirm,
    add_node_to_cluster,
    do_node_local_request
)


def _update_db_doc_with_new_node(node_details, db_name, new_node):
    db_doc = do_node_local_request(node_details, '_dbs/{}'.format(db_name))
    by_node = db_doc['by_node']
    if new_node in by_node:
        print('  Node "{}" already has shards for db "{}"'.format(new_node, db_name))
        return

    shards_for_new_node = None
    for node_name, shards in by_node.items():
        if args.control_node_ip in node_name:
            shards_for_new_node = shards
            break

    if not shards_for_new_node:
        print('Unable to find shards for db {}'.format(db_name))
        return

    print('  Adding shards to new node:\n')

    db_doc['by_node'][new_node] = shards_for_new_node

    for shard in shards_for_new_node:
        current_nodes = db_doc['by_range'][shard]
        if new_node not in current_nodes:
            print('    {}'.format(shard))
            current_nodes.append(new_node)
        else:
            print('    Node already had shard: {}'.format(shard))

    print('  Updating db config for {}'.format(db_name))
    do_node_local_request(node_details, '_dbs/{}'.format(db_name), method='put', json=db_doc)


def _add_node(node_details, new_node):
    if not is_node_in_cluster(node_details, new_node):
        if confirm("Node {} is not part of the cluster. Do you want to add it?".format(new_node)):
            add_node_to_cluster(node_details, new_node)


if __name__ == '__main__':
    parser = get_arg_parser('Replicate DB shards to a new node')
    parser.add_argument('--new-node', dest='new_node', required=True,
                        help='New node e.g. couchdb@node-ip')
    parser.add_argument('--database', dest='database', required=True,
                        help='Database to replicate')
    args = parser.parse_args()

    node_details = node_details_from_args(args)
    check_connection(node_details)

    new_node = args.new_node
    database = args.database
    _add_node(node_details, new_node)

    if not confirm("Have you copied the shard files from {} to {}?".format(node_details.ip, new_node)):
        line = "=" * 40
        print(line)
        print("Copy the shard files to the new node before updating couchdb2 with new node config.")
        print(line)
        sys.exit(1)

    if confirm('Add shards from db "{}" to new node?'.format(database)):
        _update_db_doc_with_new_node(node_details, database, new_node)
