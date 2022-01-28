from django.core.management.base import BaseCommand, CommandError
from corehq.apps.es.case_search import CaseSearchES
import timeit
import heapq
import json


# Returns min, max, average of test suite results list
def get_stats(results_list):
    n = len(results_list)
    min = heapq.heappop(heapq.heapify(results_list))
    max = heapq.heappop(heapq._heapify_max(results_list))
    avg = sum(min) / n
    return min, max, avg


def run_baseline_query(query_obj):
    print("Running baseline query...")
    result = query_obj.run().total
    print("Done!")
    return result


def run_test_queries(query_obj, repeats):
    results = []
    print("Running test queries...")
    for _ in range(repeats):
        results.append(results=timeit.timeit(query_obj.run))
    print("Done!")
    return results


def define_baseline_query(domain, case_type=None):
    if case_type is None:
        query_obj = (CaseSearchES()
            .domain(domain))
    else:
        query_obj = (CaseSearchES()
            .domain(domain)
            .case_type(case_type))
    return query_obj


def append_baseline_query(query_obj, props, operator):
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
    query_obj.set_query(script)
    return query_obj


class Command(BaseCommand):
    help = "Run test queries for perfomance benchmarks for comparison script queries."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('-ct', '--type', dest='type')
        parser.add_argument('-cp', '--properties', dest='props', nargs=2)
        parser.add_argument('-n', dest='n', default=1)

        # operator arguments, only one of these is permitted
        parser.add_argument('-eq', dest='equals', action='store_true')
        parser.add_argument('-neq', dest='not_equals', action='store_true')
        parser.add_argument('-gt', dest='greater_than', action='store_true')
        parser.add_argument('-lt', dest='less_than', action='store_true')
        parser.add_argument('-gte', dest='greater_equal', action='store_true')
        parser.add_argument('-lte', dest='less_equal', action='store_true')

        parser.add_argument('--verbose', dest="verbose", action='store_true')
        parser.add_argument('--analyze', dest="analyze", action='store_true')
        parser.add_argument('--profile', dest="profile", action='store_true')

    def handle(self, *args, **kwargs):
        domain = kwargs['domain']
        case_type = kwargs['type'] if kwargs['type'] else None
        props = kwargs['props']
        repeats = kwargs['n']
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
            raise CommandError('Only one operator flag may be invoked (-eq, -neq, -gt, -lt, -gte, -lte)')
        if len(props) != 2:
            raise CommandError("'properties' flag requires exactly 2 arguments")

        operator = operator_keylist[operator_valuelist.index(True)]

        # Need need to get baseline amount of cases that are being against for context
        # Define and run query with only domain and case_type specified
        query_obj = define_baseline_query(domain, case_type)
        baseline_amt = run_baseline_query(query_obj)

        # Define, run, and analyze the test query
        query_obj = append_baseline_query(query_obj, props, operator)
        test_results = run_test_queries(query_obj, repeats=repeats)
        min, max, avg = get_stats(test_results)

        type_str = f"{case_type}s in" if case_type else "All cases in"
        query_str = query_obj.get_query() if kwargs['verbose'] else (
            f"QUERY: {type_str} {domain} where {props[0]} {operator} {props[1]}"
        )

        # if 'profile' flag is invoked, print out profiled results
        if kwargs['profile']:
            query_obj.enable_profiling()
            profiled_hits = query_obj.run().raw
            print("=" * 8 + "PROFILED QUERY RESULTS " + "=" * 8)
            print(json.dumps(profiled_hits.get('profile', {}), indent=2))

        # print out results
        print("=" * 8 + " SCRIPT QUERY TEST " + "=" * 8)
        print(query_str)
        print(f"BASELINE: {baseline_amt} cases")
        print(f"MIN RUNTIME: {min} | MAX RUNTIME: {max} | AVG RUNTIME: {avg}")
        return None
