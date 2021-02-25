from corehq.apps.es import CaseSearchES

from .core import UserError, serialize_es_case


def get_list(domain, params):
    res = (CaseSearchES()
           .domain(domain)
           .run()
           .hits)
    return [serialize_es_case(case) for case in res]
