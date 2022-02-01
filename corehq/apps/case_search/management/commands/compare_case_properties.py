from django.core.management.base import BaseCommand, CommandError
from corehq.apps.es.case_search import CaseSearchES
from corehq.util.markup import SimpleTableWriter, TableRowFormatter, CSVRowFormatter
import time
import json


# Returns min, max, average of test suite results list
def get_stats(results_list):
    n = len(results_list)
    if n == 1:
        return results_list[0], results_list[0], results_list[0]
    min_value = min(results_list)
    max_value = max(results_list)
    avg_value = sum(results_list) / n
    return min_value, max_value, avg_value


def run_baseline_query(query_obj):
    print("\nRunning baseline query...")
    result = query_obj.count()
    print("Done!")
    return result


def run_test_queries(query_obj, repeats):
    results = []
    tooks = []
    hits = query_obj.run().total
    print("Running test queries...")
    for _ in range(repeats):
        t1 = time.time()
        tooks.append(query_obj.run().raw['took'])
        t2 = time.time()
        results.append(t2 - t1)
    print("Done!\n")
    return results, tooks, hits


def define_baseline_query(domain, case_type=None):
    if case_type is None:
        query_obj = (CaseSearchES()
            .domain(domain))
    else:
        query_obj = (CaseSearchES()
            .domain(domain)
            .case_type(case_type))
    query_obj.size(10)
    return query_obj


def define_test_query(domain, case_type, props, operator):
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
    query_obj = define_baseline_query(domain, case_type)
    query_obj.set_query(script)
    return query_obj


class Command(BaseCommand):
    help = "Run test queries for perfomance benchmarks for comparison script queries."

    def add_arguments(self, parser):
        parser.add_argument('domain', help='define domain to query against')
        parser.add_argument('-ct', '--type', dest='type', help='define case type to query against')
        parser.add_argument('-cp', '--properties', dest='props', nargs=2,
            help='define case properties to compare')
        parser.add_argument('-n', dest='n', default=1, type=int, help='set number of query attempts')

        # operator arguments, only one of these is permitted
        parser.add_argument('-eq', dest='equals', action='store_true', help='set operator to ==')
        parser.add_argument('-neq', dest='not_equals', action='store_true', help='set operator to !=')
        parser.add_argument('-gt', dest='greater_than', action='store_true', help='set operator to >')
        parser.add_argument('-lt', dest='less_than', action='store_true', help='set operator to <')
        parser.add_argument('-gte', dest='greater_equal', action='store_true', help='set operator to >=')
        parser.add_argument('-lte', dest='less_equal', action='store_true', help='set operator to <=')

        parser.add_argument('--verbose', dest="verbose", action='store_true', help='print out raw ES query')
        parser.add_argument('--profile', dest="profile", action='store_true', help='print out query profile')
        parser.add_argument('--csv', dest='csv', action='store_true', help='change table row format to csv')

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

        # Need need to get baseline amount of cases that are being queriied against for context
        # Define and run query with only domain and case_type defined
        query_obj = define_baseline_query(domain, case_type)
        baseline_amt = run_baseline_query(query_obj)

        # Define, run, and analyze the test query
        test_query_obj = define_test_query(domain, case_type, props, operator)
        test_results, took_results, hits = run_test_queries(test_query_obj, repeats=repeats)
        min_value, max_value, avg_value = get_stats(test_results)
        min_took, max_took, avg_took = get_stats(took_results)

        type_str = f"{case_type}s in" if case_type else "All cases in"
        query_str = query_obj.raw_query if kwargs['verbose'] else (
            f"QUERY: {type_str} {domain} where {props[0]} {operator} {props[1]}"
        )

        # if 'profile' flag is invoked, print out query profile
        if kwargs['profile']:
            query_obj.enable_profiling()
            profiled_hits = query_obj.run().raw
            print("=" * 8 + "PROFILED QUERY RESULTS " + "=" * 8)
            print(json.dumps(profiled_hits.get('profile', {}), indent=2))

        row_formatter = CSVRowFormatter() if kwargs['csv'] else TableRowFormatter([8, 12, 12, 12])
        writer = SimpleTableWriter(
            self.stdout,
            row_formatter
        )

        # print out results
        print("=" * 8 + " SCRIPT QUERY TEST " + "=" * 8)
        print(query_str)
        print(f"BASELINE: {baseline_amt} cases")
        print(f"MATCHED: {hits} cases" + "\n")
        print("=" * 22 + " RESULTS " + "=" * 22)
        writer.write_headers(['', 'MIN', 'MAX', 'AVG'])
        writer.write_rows([
            [
                'TOOK',
                f"{min_took} ms",
                f"{max_took} ms",
                f"{avg_took} ms"
            ],
            [
                'RUNTIME',
                f"{(min_value * 1000):.4g} ms",
                f"{(max_value * 1000):.4g} ms",
                f"{(avg_value * 1000):.4g} ms"
            ]
        ])
        return None
