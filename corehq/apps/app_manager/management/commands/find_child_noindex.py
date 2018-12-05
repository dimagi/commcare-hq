"""
Find cases that could be missing a parent index.

NOTE: This script cannot identify which are parent cases and which are
children.

Generate a list of cases (both parent and child cases) and dump it as
YAML:

    $ ./manage.py find_child_noindex > cases.yaml
    ....

Limit domains:

    $ ./manage.py find_child_noindex -d demo -d foo 2>/dev/null
    ---
    domain: demo
    case_types:
      human: [71bc56d9-4baa-4c3a-a388-c64e32b689a1, 13b7e8e0-f928-4ade-a04c-512f8863ce83,
        695f3db9-62ac-42f3-872b-1bcc55099aa8]

Just return the domain and case types:

    $ ./manage.py find_child_noindex -x 2>/dev/null
    ---
    domain: demo
    case_types: [human]

"""
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import sys

import six
import yaml
from couchdbkit import BadValueError
from django.core.management.base import BaseCommand

from casexml.apps.case.const import DEFAULT_CASE_INDEX_IDENTIFIERS, CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseBlock, ChildIndexAttrs
from casexml.apps.case.util import post_case_blocks
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.models import Module
from corehq.apps.domain.models import Domain
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface


def read_infile(filename, domains):
    with open(filename) as infile:
        for doc in yaml.load_all(infile):
            if not domains or doc['domain'] in domains:
                yield doc['domain'], doc['case_types']


def find_domain_cases(domains, include_cases=True):
    if not domains:
        domains = [row['key'] for row in Domain.get_all(include_docs=False)]
    for domain in domains:
        print('.', end='', file=sys.stderr)  # Use STDERR so we can redirect STDOUT without dots
        form_accessors = FormAccessors(domain)
        form_processor = FormProcessorInterface(domain)
        case_db = form_processor.casedb_cache(domain)
        case_types = {} if include_cases else []
        try:
            for app in get_apps_in_domain(domain, include_remote=False):
                for module in app.get_modules():
                    if isinstance(module, Module):
                        case_type = module.case_type
                        subcase_types = module.get_subcase_types()
                        if case_type in subcase_types:
                            if include_cases:
                                case_types.setdefault(case_type, [])
                                for form in module.get_forms():
                                    if 'subcases' in form.active_actions():
                                        xform_ids = list(form_accessors.iter_form_ids_by_xmlns(form.xmlns))
                                        xforms = form_accessors.get_forms(xform_ids)
                                        cases = form_processor.get_cases_from_forms(case_db, xforms)
                                        case_types[case_type].extend(cases)
                            else:
                                case_types.append(case_type)
            if case_types:
                yield domain, case_types
        except BadValueError:
            print('\nget_apps_in_domain raised BadValueError for domain "{}"'.format(domain), file=sys.stderr)
        print('\n', file=sys.stderr)


def deep_encode(value, encoding):
    """
    Traverses value and encodes all unicode.

    Returns dict subclasses as dicts and other (non-string) iterables as lists.
    """
    if isinstance(value, six.text_type):
        return value.encode(encoding)
    if isinstance(value, dict):
        return {deep_encode(k, encoding): deep_encode(value[k], encoding) for k in value}
    if hasattr(value, '__iter__'):
        return [deep_encode(v, encoding) for v in value]
    return value


def update_child_cases(domain, case_types):
    if not isinstance(case_types, dict):
        raise ValueError('Give me case IDs')
    for case_type in case_types:
        cases = case_types[case_type]
        parents = determine_parents(cases)  # TODO: Determine parents and children; may require magic
        for parent_id in parents:
            for child_id in parents[parent_id]:
                identifier = DEFAULT_CASE_INDEX_IDENTIFIERS[CASE_INDEX_CHILD]
                case_block = CaseBlock(
                    case_id=child_id,
                    case_type=case_type,
                    index={
                        identifier: ChildIndexAttrs(
                            case_type=case_type,
                            case_id=parent_id,
                            relationship=CASE_INDEX_CHILD,
                        )
                    }
                ).as_xml()
                post_case_blocks([case_block], {'domain': domain})


class Command(BaseCommand):
    help = 'Find child cases that have been created without a parent index'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--domain', action='append', dest='domains')
        parser.add_argument('-f', '--fix', action='store_true')
        parser.add_argument('-i', '--infile', metavar='YAML_FILE')
        parser.add_argument('-x', '--exclude-cases', action='store_true', dest='exclude_cases')

    def handle(self, domains, fix, infile, exclude_cases, **options):
        if infile:
            domain_casetypes = read_infile(infile, domains)
        else:
            domain_casetypes = find_domain_cases(domains, not exclude_cases)

        for domain, case_types in domain_casetypes:
            yaml.dump({
                b'domain': domain.encode('utf-8'),
                b'case_types': deep_encode(case_types, 'utf-8'),
            }, sys.stdout, explicit_start=b'---')
            if fix and not exclude_cases:
                update_child_cases(domain, case_types)  # This is not going to work
