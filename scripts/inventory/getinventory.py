#!/usr/bin/env python
"""
Get server hostname or IP address for the given inventory file and group.

The server name or IP is printed on stdout on success.
Errors and help output are printed on stderr.
"""
from __future__ import print_function
import os
import sys
import argparse
from os.path import dirname

ROOT = dirname(dirname(dirname(os.path.abspath(__file__))))


class ArgParser(argparse.ArgumentParser):

    def print_help(self, stream=sys.stderr):
        # print help to stderr by default
        super(ArgParser, self).print_help(stream)


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
    servers = read_inventory_file(
        os.path.join(ROOT, 'fab', 'inventory', instance))
    return servers[group]


def main():
    prog = os.environ.get("SCRIPT", sys.argv[0])
    parser = ArgParser(
        prog=prog,
        usage="{prog} [-h] environment [user@]group[:n] [{uprog}_ARGS]".format(
            prog=prog,
            uprog=prog.rsplit("/", 1)[-1].upper(),
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("environment",
        help="Environment: production, staging, ...")
    parser.add_argument("group",
        help="Server group: postgresql, proxy, webworkers, ... The server "
             "group may be prefixed with 'username@' to login as a specific "
             "user and may be terminated with ':<n>' to choose one of "
             "multiple servers if there is more than one in the group. "
             "For example: webworkers:0 will pick the first webworker.")

    args = parser.parse_args()
    group = args.group
    if "@" in group:
        username, group = group.split('@', 1)
        username += "@"
    else:
        username = ""
    if ':' in group:
        group, index = group.rsplit(':', 1)
        try:
            index = int(index)
        except (TypeError, ValueError):
            parser.error("Non-numeric group index: {}".format(index))
    else:
        index = None

    try:
        servers = get_instance_group(args.environment, group)
    except IOError as err:
        parser.error(err)
    except KeyError as err:
        parser.error("Unknown group: {}\n".format(group))

    if index is not None and index > len(servers) - 1:
        sys.stderr.write(
            "Invalid group index: {index}\n"
            "Please specify a number between 0 and {max} inclusive\n"
            .format(index=index, max=len(servers) - 1)
        )
        sys.exit(1)
    if len(servers) > 1:
        if index is None:
            sys.stderr.write(
                "There are {num} servers in the '{group}' group\n"
                "Please specify the index of the server. Example: {group}:0\n"
                .format(num=len(servers), group=group)
            )
            sys.exit(1)
        server = servers[index]
    else:
        server = servers[index or 0]

    print(username + server)


if __name__ == "__main__":
    main()
