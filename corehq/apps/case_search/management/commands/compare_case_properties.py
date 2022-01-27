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
        parser.add_argument('-eq', dest='equals', action='store_true')
        parser.add_argument('-neq', dest='not_equals', action='store_true')
        parser.add_argument('-gt', dest='greater_than', action='store_true')
        parser.add_argument('-lt', dest='less_than', action='store_true')
        parser.add_argument('-gteq', dest='greater_equal', action='store_true')
        parser.add_argument('-lteq', dest='less_equal', action='store_true')

    def handle(self, *args, **kwargs):
        domain = kwargs['domain']
        case_type = kwargs['type'] if kwargs['type'] else None
        props = kwargs['props']
        operators = {
            "==": kwargs['equals'],
            "!=": kwargs['not_equals'],
            ">": kwargs['greater_than'],
            "<": kwargs['less_than'],
            ">=": kwargs['greater_equal'],
            "<=": kwargs['less_equal']
        }
        operator_valuelist = list(operators.values())
        operator_keylist = list(operators.keys())

        if operator_valuelist.count(True) != 1:
            raise Exception('Exception: only one operator flag may be invoked (-eq, -neq, -gt, -lt, -gteq, -lteq)')
        if len(props) != 2:
            raise ValueError('Value Error exception thown: 2 arguments required for properties flag')

        operator = operator_keylist[operator_valuelist.index(True)]
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
