#!/usr/bin/env python
import os


def read_inventory_file(filename):
    """
    filename is a path to an ansible inventory file

    returns a mapping of group names ("webworker", "proxy", etc.)
    to lists of hosts (ip addresses)

    """
    from ansible.inventory import InventoryParser

    return {name: [host.name for host in group.get_hosts()]
            for name, group in InventoryParser(filename).groups.items()}


def get_instance_group(instance, group):
    servers = read_inventory_file(os.path.join('fab', 'inventory', instance))
    return servers[group]

if __name__ == '__main__':
    import sys
    instance = sys.argv[1]
    group = sys.argv[2]
    servers = get_instance_group(instance, group)
    for server in servers:
        print server
