from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import random
import string

from six.moves import range

from django.core.management import BaseCommand

from casexml.apps.case.mock.mock import CaseFactory
from corehq.apps.domain.models import Domain
from corehq.util.log import with_progress_bar

NUMBER_OF_CASES = [100, 10000, 100000]
NUMBER_OF_CASE_PROPERTIES = [0, 10, 100]
LENGTHS_OF_CASE_PROPERTIES = [1, 10, 100, 1000]


class Command(BaseCommand):

    def handle(self, *args, **options):
        for number_of_cases in NUMBER_OF_CASES:
            domain_name = 'odata-load-testing-%s' % number_of_cases
            assert Domain.get_by_name(domain_name)
            case_factory = CaseFactory(domain_name)
            for number_of_case_properties in NUMBER_OF_CASE_PROPERTIES:
                for length_of_case_property in LENGTHS_OF_CASE_PROPERTIES:
                    case_type = 'num_prop_%s_len_prop_%s' % (
                        number_of_case_properties, length_of_case_property
                    )
                    print('Creating...')
                    print('Cases: %s' % number_of_cases)
                    print('Case properties: %s' % number_of_case_properties)
                    print('Length: %s' % length_of_case_property)
                    for case_number in with_progress_bar(range(number_of_cases)):
                        case_name = '%s-%s' % (case_type, case_number)
                        case_properties = {
                            'p%s' % property_number: ''.join(
                                random.choice(string.ascii_lowercase) for _ in range(length_of_case_property)
                            )
                            for property_number in range(number_of_case_properties)
                        }
                        case_factory.create_case(
                            case_type=case_type,
                            case_name=case_name,
                            update=case_properties,
                        )
