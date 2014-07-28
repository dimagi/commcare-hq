import os
import json

def get_domain_configuration(domain):
    with open(os.path.join(os.path.dirname(__file__), 'resources', '/%s.json' % (domain))) as f:
        return json.loads(f.read())
