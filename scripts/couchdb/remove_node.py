from __future__ import absolute_import
import sys

from .utils import (
    do_couch_request,
    get_arg_parser,
    node_details_from_args,
    check_connection,
    is_node_in_cluster,
    confirm,
    remove_node_from_cluster,
    do_node_local_request,
    get_membership)


def _remove_shards_from_node(node_details, db_name, node_to_remove):
    db_doc = do_node_local_request(node_details, '_dbs/{}'.format(db_name))
    by_node = db_doc['by_node']
    if node_to_remove not in by_node:
        print('  Node "{}" has no shards for db "{}"'.format(node_to_remove, db_name))
        return True

    if not confirm('Remove shards from db "{}" for "{}"?'.format(db_name, node_to_remove)):
        return False

    shards_to_remove = by_node.pop(node_to_remove)
    if not by_node:
        raise Exception("Can't remove node {} from db {} as there are no other dbs that have it's shards".format(
            node_to_remove, db_name
        ))

    if not shards_to_remove:
        print('Unable to find shards for db {} belonging to node {}'.format(db_name, node_to_remove))
        return False

    print('  Removing shards from node:\n')

    for shard in shards_to_remove:
        shard_nodes = db_doc['by_range'][shard]
        if node_to_remove in shard_nodes:
            shard_nodes.remove(node_to_remove)
            print('    {}'.format(shard))
        else:
            print('    Shard {} missing from node: {}'.format(shard, node_to_remove))

    print('  Updating db config for {}'.format(db_name))
    do_node_local_request(node_details, '_dbs/{}'.format(db_name), method='put', json=db_doc)
    return True


def _remove_node(node_details, new_node):
    if is_node_in_cluster(node_details, new_node):
        remove_node_from_cluster(node_details, new_node)
    else:
        print('Node not part of the cluster according to {}'.format(node_details.ip))


if __name__ == '__main__':
    parser = get_arg_parser('Remove a node from the cluster')
    parser.add_argument('--node-to-remove', dest='node_to_remove', required=True,
                        help='Node to remove from the cluster e.g. couchdb@node-ip')
    args = parser.parse_args()

    node_details = node_details_from_args(args)
    check_connection(node_details)

    node_to_remove = args.node_to_remove

    if not is_node_in_cluster(node_details, node_to_remove):
        print('Node already removed from cluster')
        sys.exit(0)

    dbs = do_couch_request(node_details, '_all_dbs')
    remove_from_cluster = True
    for db_name in dbs:
        if db_name.startswith('_'):
            # TODO: remove this once there's a workaround for https://github.com/apache/couchdb/issues/858
            print("Skipping db {}".format(db_name))
            continue
        shards_removed = _remove_shards_from_node(node_details, db_name, node_to_remove)
        remove_from_cluster &= shards_removed

    if remove_from_cluster:
        if confirm("Remove node {} completely from cluster?".format(node_to_remove)):
            _remove_node(node_details, node_to_remove)
            print('Cluster membership:\n{}'.format(get_membership(node_details)))
    else:
        print("Node could not be removed from cluster as it may still have shards")
