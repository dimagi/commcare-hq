from django.core.management.base import BaseCommand
from corehq.apps.es.case_search import CaseSearchES
import timeit


def define_query(domain, props, operator, case_type=None):
    script = {
        "bool": {
            "must": [
                {
                    "script": {
                        "script": "def val = _source['case_properties'].find{ it -> it.key == '%s' }?.value;"
                        "_source['case_properties'].find{ it -> it.key == '%s' }?.value %s val;"
                        % (props[0], props[1], operator),
                        "lang": "groovy"
                    }
                }
            ]
        }
    }
    if case_type:
        query_obj = (CaseSearchES()
            .domain(domain)
            .set_query(script))
    else:
        query_obj = (CaseSearchES()
            .domain(domain)
            .case_type(case_type)
            .set_query(script))
    return query_obj


class Command(BaseCommand):
    help = "Run test queries for perfomance benchmarks for comparison script queries."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('-ct', '--type', dest='type', type=str)
        parser.add_argument('-cp', '--properties', dest='props', nargs='+', type=str)
        parser.add_argument('-op', '--operator', dest='operator', type=str)

    def handle(self, *args, **kwargs):
        domain = kwargs['domain']
        case_type = kwargs['type'] if kwargs['type'] else None
        props = kwargs['props']
        operator = kwargs['operator']

        if len(props) != 2:
            raise ValueError('Value Error exception thown: 2 arguments are needed for properties flag')

        query_obj = define_query(domain, props, operator, case_type)
        type_str = f"{case_type}s in" if case_type else "All cases in"

        print("=" * 8 + " SCRIPT QUERY TEST " + "=" * 8)
        print(f"QUERY: {type_str} {domain} where {props[0]} {operator} {props[1]}")
        results = timeit.timeit(
            lambda: print("HITS: " + str(query_obj.run().total)),
            number=1
        )
        print(f"RUNTIME: {results}")
        return None
