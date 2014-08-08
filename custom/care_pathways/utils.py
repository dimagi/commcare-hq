import os
import json

def get_domain_configuration(domain):
    with open(os.path.join(os.path.dirname(__file__), 'resources/%s.json' % (domain))) as f:
        return json.loads(f.read())

def is_mapping(prop, domain):
    return any(d['val'] == prop for d in get_mapping(domain))

def is_domain(prop, domain):
    return any(d['val'] == prop for d in get_domains(domain))

def is_practice(prop, domain):
    return any(d['val'] == domain for d in get_pracices(domain))

def get_mapping(domain_name):
    value_chains = get_domain_configuration(domain_name)['by_type_hierarchy']
    return list({'val': vc['val'], "text": vc['text']} for vc in value_chains)

def get_domains_with_next(domain_name):
    configuration = get_domain_configuration(domain_name)['by_type_hierarchy']
    domains = []
    for chain in configuration:
        domains.extend(chain['next'])
    return domains


def get_domains(domain_name):
    domains = get_domains_with_next(domain_name)
    return list({'val': d['val'], "text": d['text']} for d in domains)


def get_pracices(case):
    domains = get_domains_with_next(case)
    practices = []
    for domain in domains:
        practices.extend(domain['next'])
    return list({'val': p['val'], "text": p['text']} for p in practices)

