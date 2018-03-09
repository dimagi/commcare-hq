#!/usr/bin/env python
"""
Utilities for administering elasticsearch

These can be run locally when connected to the VPN
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from collections import namedtuple
import json
import sys

from elasticsearch import Elasticsearch
from elasticsearch.client import ClusterClient, NodesClient, CatClient, IndicesClient
from six.moves import input


def pprint(data):
    print(json.dumps(data, indent=4))


def confirm(msg):
    if input(msg + "\n(y/n)") != 'y':
        sys.exit()


Node = namedtuple("Node", "name node_id docs settings")


def get_nodes_info(es):
    nc = NodesClient(es)
    stats = nc.stats(metric="indices", index_metric="docs")
    info = nc.info()
    return [
        Node(
            name=data['name'],
            node_id=node_id,
            docs=data['indices']['docs'],
            settings=info['nodes'][node_id]['settings'],
        )
        for node_id, data in stats['nodes'].items()
    ]


def cluster_status(es):
    cluster = ClusterClient(es)
    print("\nCLUSTER HEALTH")
    pprint(cluster.health())
    print("\nPENDING TASKS")
    pprint(cluster.pending_tasks())
    print("\nNODES")
    for node in get_nodes_info(es):
        print(node.name, node.docs)
    print("\nSHARD ALLOCATION")
    cat = CatClient(es)
    print(cat.allocation(v=True))


def shard_status(es):
    cat = CatClient(es)
    print(cat.shards(v=True))


def cluster_settings(es):
    cluster = ClusterClient(es)
    pprint(cluster.get_settings())


def index_settings(es):
    indices = IndicesClient(es)
    pprint(indices.get_settings(flat_settings=True))


def create_replica_shards(es):
    # https://www.elastic.co/guide/en/elasticsearch/reference/2.3/indices-update-settings.html
    indices = IndicesClient(es)
    pprint(indices.put_settings({"index.number_of_replicas": 1}, "_all"))


def cancel_replica_shards(es):
    indices = IndicesClient(es)
    pprint(indices.put_settings({"index.number_of_replicas": 0}, "_all"))



def decommission_node(es):
    cluster = ClusterClient(es)
    print("The nodes are:")
    nodes = get_nodes_info(es)
    for node in nodes:
        print(node.name, node.docs)
    confirm("Are you sure you want to decommission a node?")
    node_name = input("Which one would you like to decommission?\nname:")
    names = [node.name for node in nodes]
    if node_name not in names:
        print("You must enter one of {}".format(", ".join(names)))
        return
    confirm("This will remove all shards from {}, okay?".format(node_name))
    cmd = {"transient": {"cluster.routing.allocation.exclude._name": node_name}}
    pprint(cluster.put_settings(cmd))
    print("The node is now being decommissioned.")


def force_zone_awareness(es):
    cluster = ClusterClient(es)
    print("NODE SETTINGS:")
    for node in get_nodes_info(es):
        pprint(node.settings)
    zones = input("\nEnter the zone names, separated by a comma\n")
    confirm("Are you sure these zones exist?")
    cmd = {"persistent": {"cluster.routing.allocation.awareness.force.zone.values": zones,
                          "cluster.routing.allocation.awareness.attributes": "zone"}}
    print("This will add the following settings")
    pprint(cmd)
    confirm("Okay?")
    pprint(cluster.put_settings(cmd))
    print("Finished")


def clear_zone_awareness(es):
    # There doesn't appear to be a proper way to unset settings
    # https://github.com/elastic/elasticsearch/issues/6732
    cluster = ClusterClient(es)
    cmd = {"persistent": {"cluster.routing.allocation.awareness.force.zone.values": "",
                          "cluster.routing.allocation.awareness.attributes": ""}}
    confirm("Remove the allocation awareness settings from the cluster?")
    pprint(cluster.put_settings(cmd))
    print("Cleared")


def pending_tasks(es):
    cluster = ClusterClient(es)
    pprint(cluster.pending_tasks())


commands = {
    'cluster_status': cluster_status,
    'cluster_settings': cluster_settings,
    'index_settings': index_settings,
    'decommission_node': decommission_node,
    'shard_status': shard_status,
    'create_replica_shards': create_replica_shards,
    'cancel_replica_shards': cancel_replica_shards,
    'force_zone_awareness': force_zone_awareness,
    'clear_zone_awareness': clear_zone_awareness,
    'pending_tasks': pending_tasks,
}


def main():
    parser = ArgumentParser(description=__doc__, formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('host_url')
    parser.add_argument('command', choices=list(commands))
    args = parser.parse_args()
    es = Elasticsearch([{'host': args.host_url, 'port': 9200}])
    commands[args.command](es)


if __name__ == "__main__":
    main()
