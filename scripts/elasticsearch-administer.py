#!/usr/bin/env python
"""
Utilities for administering elasticsearch

These can be run locally when connected to the VPN
"""
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from collections import namedtuple
import json
import sys

from elasticsearch import Elasticsearch
from elasticsearch.client import ClusterClient, NodesClient, CatClient


def pprint(data):
    print json.dumps(data, indent=4)


def confirm(msg):
    if raw_input(msg + "\n(y/n)") != 'y':
        sys.exit()


Node = namedtuple("Node", "name node_id docs")


def get_nodes_info(es):
    nc = NodesClient(es)
    stats = nc.stats(metric="indices", index_metric="docs")
    return [Node(info['name'], node_id, info['indices']['docs'])
            for node_id, info in stats['nodes'].items()]


def cluster_status(es):
    cluster = ClusterClient(es)
    print "\nCLUSTER HEALTH"
    pprint(cluster.health())
    print "\nPENDING TASKS"
    pprint(cluster.pending_tasks())
    print "\nNODES"
    for node in get_nodes_info(es):
        print node.name, node.docs
    print "\nSHARD ALLOCATION"
    cat = CatClient(es)
    print cat.allocation(v=True)


def shard_status(es):
    cat = CatClient(es)
    print cat.shards(v=True)


def cluster_settings(es):
    cluster = ClusterClient(es)
    pprint(cluster.get_settings())


def decommission_node(es):
    cluster = ClusterClient(es)
    print "The nodes are:"
    nodes = get_nodes_info(es)
    for node in nodes:
        print node.name, node.docs
    confirm("Are you sure you want to decommission a node?")
    node_name = raw_input("Which one would you like to decommission?\nname:")
    names = [node.name for node in nodes]
    if node_name not in names:
        print "You must enter one of {}".format(", ".join(names))
        return
    confirm("This will remove all shards from {}, okay?".format(node_name))
    cmd = {"transient": {"cluster.routing.allocation.exclude._name": node_name}}
    pprint(cluster.put_settings(cmd))
    print "The node is now being decommissioned."


commands = {
    'cluster_status': cluster_status,
    'cluster_settings': cluster_settings,
    'decommission_node': decommission_node,
    'shard_status': shard_status,
}


def main():
    parser = ArgumentParser(description=__doc__, formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('host_url')
    parser.add_argument('command', choices=commands.keys())
    args = parser.parse_args()
    es = Elasticsearch([{'host': args.host_url, 'port': 9200}])
    commands[args.command](es)


if __name__ == "__main__":
    main()
