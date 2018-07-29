#!/usr/bin/env python
"""
Utilities for administering kafka.

This can be run locally when connected to the VPN.
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
from string import ljust
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from kafka import KafkaClient


def get_num_partitions(client, broker):
    return len([partition for topic in client.topic_partitions.values()
                          for partition in topic.values()
                if broker == partition.leader or broker in partition.replicas])


def print_broker_info(client):
    print(ljust("Broker ID", 10), ljust("partitions", 11), "URL")
    for broker, meta in client.brokers.items():
        print(ljust(str(broker), 10), end=' ')
        print(ljust(str(get_num_partitions(client, broker)), 11), end=' ')
        print("{}:{}".format(meta.host, meta.port))


def print_topics(client):
    """
    Prints a json representation of all available topics, suitable for the
    `kafka-reassign-partitions.sh `--topics-to-move-json-file` file.
    """
    topics_dict = {
        'topics': [{'topic': topic} for topic in client.topics],
        'version': 1,
    }
    print(json.dumps(topics_dict, indent=4))


def main():
    parser = ArgumentParser(description=__doc__, formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('host_url')
    parser.add_argument('--print_topics', action="store_true")
    args = parser.parse_args()

    url = args.host_url
    client = KafkaClient(url if ":" in url else url + ":9092")
    if args.print_topics:
        print_topics(client)
    else:
        print_broker_info(client)


if __name__ == "__main__":
    main()
