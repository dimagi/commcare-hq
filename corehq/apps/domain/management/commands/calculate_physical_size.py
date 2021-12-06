import json
import math

from django.core.management.base import BaseCommand

from corehq.apps.es import FormES, CaseSearchES, CaseES
from corehq.apps.reports.analytics.esaccessors import (
    get_case_types_for_domain_es,
)
from couchforms.analytics import (
    get_all_xmlns_app_id_pairs_submitted_to_in_domain,
)


class Command(BaseCommand):
    help = "Estimates the physical size of one or more domains' forms and cases."

    def add_arguments(self, parser):
        parser.add_argument(
            'domains',
            help="a list of domains",
            nargs='+',
        )
        parser.add_argument(
            '--sample_size',
            help="the number of samples to average over per form/case type",
        )
        parser.add_argument(
            '--use_case_search',
            action='store_true',
            help="use the CaseSearchES index for calculating case size",
        )
        parser.add_argument(
            '--only_forms',
            action='store_true',
            help="show only form stats",
        )
        parser.add_argument(
            '--only_cases',
            action='store_true',
            help="show only case stats",
        )

    def handle(self, domains, **options):
        final_num_forms = 0
        final_num_cases = 0
        final_size_forms = 0
        final_size_cases = 0

        sample_size = int(options['sample_size'] or 10)
        use_case_search = options.get('use_case_search', False)
        show_only_forms = options.get('only_forms', False)
        show_only_cases = options.get('only_cases', False)

        if not show_only_cases:
            self.stdout.write(f"\n\nCalculating size of forms with a sample "
                            f"size of {sample_size} per XMLNS...")

        if not show_only_forms:
            self.stdout.write(f"\n\nCalculating size of cases with a sample "
                            f"size of {sample_size} per Case Type...")
            if use_case_search:
                self.stdout.write("The Case search index is being used.")

        for domain in domains:
            if not show_only_cases:
                num_forms, size_of_forms = _get_form_size_stats(domain, sample_size)
                final_num_forms += num_forms
                final_size_forms += size_of_forms

                self.stdout.write(f"\n{domain} has {num_forms} forms, "
                                f"taking up approximately {size_of_forms} bytes "
                                f"({_get_human_bytes(size_of_forms)}) of "
                                f"physical space.")

            if not show_only_forms:
                num_cases, size_of_cases = _get_case_size_stats(
                    domain, sample_size, use_case_search
                )
                final_num_cases += num_cases
                final_size_cases += size_of_cases

                self.stdout.write(f"\n{domain} has {num_cases} cases, "
                                f"taking up approximately {size_of_cases} bytes "
                                f"({_get_human_bytes(size_of_cases)}) of "
                                f"physical space.")

        if not show_only_cases:
            self.stdout.write(f"\nThese domains have a total of {final_num_forms} forms, "
                            f"taking up approximately {final_size_forms} bytes "
                            f"({_get_human_bytes(final_size_forms)}) of physical space.")

        if not show_only_forms:
            self.stdout.write(f"\nThese domains have a total of {final_num_cases} cases, "
                            f"taking up approximately {final_size_cases} bytes "
                            f"({_get_human_bytes(final_size_cases)}) of physical space.")

        self.stdout.write("\n\nDone.\n\n")


def _get_doc_size_in_bytes(doc):
    return len(json.dumps(doc).encode("utf-8"))


def _get_totals_for_query(query):
    result = query.run()
    average_size_in_bytes = math.ceil(
        sum([_get_doc_size_in_bytes(doc)
             for doc in result.hits]) / len(result.hits)
    )
    return result.total, average_size_in_bytes


def _get_form_size_stats(domain, sample_size):
    total_bytes = 0
    total_forms = 0
    for xmlns, app_id in get_all_xmlns_app_id_pairs_submitted_to_in_domain(domain):
        query = (FormES()
                 .domain(domain)
                 .sort('received_on', desc=True)
                 .app(app_id)
                 .xmlns(xmlns)
                 .size(sample_size))
        num_forms, avg_size = _get_totals_for_query(query)
        total_bytes += num_forms * avg_size
        total_forms += num_forms
    return total_forms, total_bytes


def _get_case_size_stats(domain, sample_size, use_case_search):
    total_bytes = 0
    total_cases = 0
    index_class = CaseSearchES if use_case_search else CaseES
    for case_type in get_case_types_for_domain_es(domain, use_case_search):
        query = (index_class()
                 .domain(domain)
                 .case_type(case_type)
                 .size(sample_size))
        num_cases, avg_size = _get_totals_for_query(query)
        total_bytes += num_cases * avg_size
        total_cases += num_cases
    return total_cases, total_bytes


def _get_human_bytes(num_bytes):
    """Return the given bytes as a human friendly KB, MB, GB, or TB string
    thanks https://stackoverflow.com/questions/12523586/python-format-size-application-converting-b-to-kb-mb-gb-tb
    """
    num_bytes = float(num_bytes)
    one_kb = float(1024)
    one_mb = float(one_kb ** 2)  # 1,048,576
    one_gb = float(one_kb ** 3)  # 1,073,741,824
    one_tb = float(one_kb ** 4)  # 1,099,511,627,776

    if num_bytes < one_kb:
        return '{0} {1}'.format(bytes, 'Bytes' if 0 == num_bytes > 1 else 'Byte')
    elif one_kb <= num_bytes < one_mb:
        return '{0:.2f} KB'.format(num_bytes / one_kb)
    elif one_mb <= num_bytes < one_gb:
        return '{0:.2f} MB'.format(num_bytes / one_mb)
    elif one_gb <= num_bytes < one_tb:
        return '{0:.2f} GB'.format(num_bytes / one_gb)
    else:
        return '{0:.2f} TB'.format(num_bytes / one_tb)
