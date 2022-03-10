import ipaddress
import socket


def resolve_to_ips(hostname, port=80):
    try:
        address_tuples = socket.getaddrinfo(hostname, port)
    except socket.gaierror:
        raise CannotResolveHost(hostname)

    return [extract_ip(addr_info) for addr_info in address_tuples]


INDEX_SOCKADDR = 4
INDEX_ADDRESS = 0


def extract_ip(addr_info):
    return ipaddress.ip_address(addr_info[INDEX_SOCKADDR][INDEX_ADDRESS])


class CannotResolveHost(Exception):
    pass
