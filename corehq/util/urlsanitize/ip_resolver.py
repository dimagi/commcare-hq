from operator import itemgetter
from socket import getaddrinfo


def sort_ip_addresses(ip_addresses):
    return sorted(ip_addresses, key=itemgetter(0))


INDEX_SOCKADDR = 4
INDEX_ADDRESS = 0


def extract_ip(addr_info):
    return addr_info[INDEX_SOCKADDR][INDEX_ADDRESS]


def resolve_ip(address, port=80):
    ips = sort_ip_addresses(getaddrinfo(address, port))
    return extract_ip(ips[0])
