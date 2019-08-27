import csv342 as csv
from django.core.management import BaseCommand, call_command
from corehq.apps.receiverwrapper.util import get_app_version_info
from corehq.apps.hqcase.utils import resave_case
from corehq.apps.users.util import cached_owner_id_to_display
from corehq.elastic import ES_MAX_CLAUSE_COUNT
from corehq.apps.es.cases import CaseES
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors


class Command(BaseCommand):
    help = "Checks a domain's cases to see if they reference non existing cases"

    def add_arguments(self, parser):
        parser.add_argument('domain', nargs='+')
        parser.add_argument('--filename', dest='filename', default='badcaserefs.csv')
        parser.add_argument('--debug', action='store_true', dest='debug', default=False)
        parser.add_argument('--cleanup', action='store_true', dest='cleanup', default=False)

    def handle(self, **options):
        domain = options['domain']
        debug = options['debug']
        cleanup = options['cleanup']
        domain_query = CaseES().domain(domain)
        valid_case_ids = set(domain_query.get_ids())
        referenced_case_ids = {
            index['referenced_id']
            for hit in domain_query.source('indices.referenced_id').run().hits
            for index in hit['indices']
        }

        invalid_referenced_ids = referenced_case_ids - valid_case_ids

        if len(invalid_referenced_ids) > ES_MAX_CLAUSE_COUNT:
            print("there's a lot of invalid ids here. ES queries may not handle this well")

        cases_with_invalid_references = (
            domain_query
            .term('indices.referenced_id', invalid_referenced_ids)
            .source(['_id', 'type', 'indices', 'owner_id', 'opened_by', 'xform_ids'])
            .run().hits
        )

        with open(options['filename'], 'w', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            headers = [
                'case id',
                'case type',
                'creating form id',
                'referenced id',
                'referenced_type',
                'index relationship',
                'index identifier',
                'owner id',
                'owner name',
                'opened by id',
                'opened by name',
            ]
            if debug:
                headers.append('app version')
            writer.writerow(headers)

            for case in cases_with_invalid_references:
                for index in case['indices']:
                    if index['referenced_id'] in invalid_referenced_ids:
                        form_id = case['xform_ids'][0]
                        row = [
                            case['_id'],
                            case['type'],
                            form_id,
                            index['referenced_id'],
                            index['referenced_type'],
                            index['relationship'],
                            index['identifier'],
                            case['owner_id'],
                            cached_owner_id_to_display(case['owner_id']),
                            case['opened_by'],
                            cached_owner_id_to_display(case['opened_by']),
                        ]
                        if debug:
                            form = FormAccessors(domain=domain).get_form(form_id)
                            app_version_info = get_app_version_info(
                                domain,
                                form.build_id,
                                form.form_data['@version'],
                                form.metadata,
                            )
                            row.append(app_version_info.build_version)
                        writer.writerow(row)

        if cleanup:
            missing = set()
            deleted = set()
            exists = set()
            for invalid_id in invalid_referenced_ids:
                try:
                    case = CaseAccessors(domain).get_case(invalid_id)
                except CaseNotFound:
                    missing.add(invalid_id)
                else:
                    if case.is_deleted:
                        deleted.add(case)
                    else:
                        exists.add(case)

            for case_to_resync in exists:
                # if the case actually exists resync it to fix the es search
                resave_case(domain, case_to_resync, send_post_save_signal=False)

            if exists:
                print('resynced {} cases that were actually not deleted'.format(len(exists)))

            for case in deleted:
                # delete the deleted case's entire network in one go
                call_command('delete_related_cases', domain, case.case_id)

            for case in cases_with_invalid_references:
                for index in case['indices']:
                    if index['referenced_id'] in missing:
                        # this is just an invalid reference. no recourse but to delete the case itself
                        call_command('delete_related_cases', domain, case['_id'])
