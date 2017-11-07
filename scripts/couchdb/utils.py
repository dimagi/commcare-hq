from __future__ import absolute_import
import argparse
import getpass
from collections import namedtuple

import requests
import time
from six.moves import input

NodeDetails = namedtuple('NodeDetails', 'ip port node_local_port username password')


def do_couch_request(node_details, path, method='get', params=None, json=None):
    return _do_request(node_details, path, node_details.port, method=method, params=params, json=json)


def do_node_local_request(node_details, path, method='get', params=None, json=None):
    return _do_request(node_details, path, node_details.node_local_port, method=method, params=params, json=json)


def _do_request(node_details, path, port, method='get', params=None, json=None):
    response = requests.request(
        method=method,
        url="http://{}:{}/{}".format(node_details.ip, port, path),
        auth=(node_details.username, node_details.password),
        params=params,
        json=json,
    )
    response.raise_for_status()
    return response.json()


def get_membership(node_details):
    return do_couch_request(node_details, '_membership')


def confirm(msg):
    return input(msg + "\n(y/n)") == 'y'


def get_arg_parser(command_description):
    parser = argparse.ArgumentParser(description=command_description)
    parser.add_argument('--control-node-ip', dest='control_node_ip', required=True,
                        help='IP of an existing node in the cluster')
    parser.add_argument('--username', dest='username', required=True,
                        help='Admin username')
    parser.add_argument('--control-node-port', dest='control_node_port', default=15984,
                        help='Port of control node. Default: 15984')
    parser.add_argument('--control-node-local-port', dest='control_node_local_port', default=15986,
                        help='Port of control node for local operations. Default: 15986')
    return parser


def node_details_from_args(args):
    password = getpass.getpass('Password for "{}@{}"'.format(args.username, args.control_node_ip))
    return NodeDetails(
        args.control_node_ip, args.control_node_port, args.control_node_local_port,
        args.username, password
    )


def add_node_to_cluster(node_details, new_node):
    do_node_local_request(node_details, '_nodes/{}'.format(new_node), json={}, method='put')
    success = False
    for attempt in range(0, 3):
        success = is_node_in_cluster(node_details, new_node)
        if success:
            break
        time.sleep(1)  # wait for state to be propagated

    if not success:
        raise Exception('Node could not be added to cluster')


def remove_node_from_cluster(node_details, node_to_remove):
    node_url_path = '_nodes/{}'.format(node_to_remove)
    node_doc = do_node_local_request(node_details, node_url_path)
    do_node_local_request(node_details, node_url_path, method='delete', params={
        'rev': node_doc['_rev']
    })


def check_connection(node_details):
    do_couch_request(node_details, '')


def is_node_in_cluster(node_details, node_to_check):
    membership = get_membership(node_details)
    return node_to_check in membership['cluster_nodes']
