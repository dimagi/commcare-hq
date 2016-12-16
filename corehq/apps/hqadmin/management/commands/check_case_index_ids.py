import csv
from django.core.management import BaseCommand
from casexml.apps.case.cleanup import close_cases
from corehq.apps.receiverwrapper.util import get_app_version_info
from corehq.apps.reports.views import FormDataView
from corehq.apps.users.util import cached_owner_id_to_display
from corehq.elastic import ES_MAX_CLAUSE_COUNT
from corehq.apps.es.cases import CaseES
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.util.view_utils import absolute_reverse


class Command(BaseCommand):
    help = "Checks a domain's cases to see if they reference non existing cases"

    def add_arguments(self, parser):
        parser.add_argument('domain', nargs='+')
        parser.add_argument('--filename', dest='filename', default='badcaserefs.csv')
        parser.add_argument('--debug', action='store_true', dest='debug', default=False)
        parser.add_argument('--close-all', action='store_true', dest='close_all', default=False)

    def handle(self, *args, **options):
        domain = options['domain']
        debug = options['debug']
        close_all = options['close_all']
        domain_query = CaseES().domain(domain)
        valid_case_ids = set(domain_query.get_ids())
        referenced_case_ids = {
            index['referenced_id']
            for hit in domain_query.source('indices.referenced_id').run().hits
            for index in hit['indices']
        }

        invalid_referenced_ids = referenced_case_ids - valid_case_ids

        if len(invalid_referenced_ids) > ES_MAX_CLAUSE_COUNT:
            print "there's a lot of invalid ids here. ES queries may not handle this well"

        cases_with_invalid_references = (
            domain_query
            .term('indices.referenced_id', invalid_referenced_ids)
            .source(['_id', 'type', 'indices', 'owner_id', 'opened_by', 'xform_ids'])
            .run().hits
        )

        with open(options['filename'], 'w') as csvfile:
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

        if close_all:
            if raw_input('\n'.join([
                'Are you sure you want to close these {} cases? (y/N)'.format(len(cases_with_invalid_references)),
            ])).lower() == 'y':
                case_ids = [case['_id'] for case in cases_with_invalid_references]
                form, closed_cases = close_cases(case_ids)
                print 'closed {} cases. You can undo this by archiving this form: {}'.format(
                    len(closed_cases),
                    absolute_reverse(FormDataView.urlname, args=form.form_id)
                )
