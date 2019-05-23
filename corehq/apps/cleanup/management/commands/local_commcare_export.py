from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import json
import sys

import os
from collections import namedtuple

import dateutil
from django.core.management.base import BaseCommand, CommandError
from requests import ConnectionError
from tastypie.bundle import Bundle

from corehq.apps.api.es import ElasticAPIQuerySet, CaseES, es_search_by_params, XFormES
from corehq.apps.api.models import ESCase, ESXFormInstance
from corehq.apps.api.resources.v0_4 import CommCareCaseResource, XFormInstanceResource
from corehq.apps.api.serializers import CommCareCaseSerializer, XFormInstanceSerializer
from corehq.elastic import ESError


class MockApi(namedtuple('MockApi', 'query_set resource serializer')):

    def serialize(self, obj):
        return json.loads(self.serializer.serialize(self.resource.full_dehydrate(Bundle(obj=obj))))


def _get_case_mock(project, params):
    # this is mostly copy/paste/modified from CommCareCaseResource
    es_query = es_search_by_params(params, project)
    query_set = ElasticAPIQuerySet(
        payload=es_query,
        model=ESCase,
        es_client=CaseES(project),
    ).order_by('server_modified_on')

    return MockApi(
        query_set, CommCareCaseResource(), CommCareCaseSerializer()
    )


def _get_form_mock(project, params):
    # this is mostly copy/paste/modified from XFormInstanceResource
    include_archived = 'include_archived' in params
    es_query = es_search_by_params(params, project, ['include_archived'])
    if include_archived:
        es_query['filter']['and'].append({'or': [
            {'term': {'doc_type': 'xforminstance'}},
            {'term': {'doc_type': 'xformarchived'}},
        ]})
    else:
        es_query['filter']['and'].append({'term': {'doc_type': 'xforminstance'}})

    query_set = ElasticAPIQuerySet(
        payload=es_query,
        model=ESXFormInstance,
        es_client=XFormES(project),
    ).order_by('received_on')
    return MockApi(
        query_set, XFormInstanceResource(), XFormInstanceSerializer()
    )


def _get_mock_api(resource, project, params):
    if resource == 'case':
        return _get_case_mock(project, params)
    elif resource == 'form':
        return _get_form_mock(project, params)
    else:
        raise ValueError("Unknown/unsupported resource type '{}'".format(resource))


def local_on_backoff(details):
    from commcare_export.commcare_hq_client import on_backoff
    on_backoff(details)


def local_on_giveup(details):
    from commcare_export.commcare_hq_client import on_giveup
    on_giveup(details)


class LocalCommCareHqClient(object):
    """
    Like CommCareHqClient but for a local environment
    """
    def __init__(self, url, project, limit, checkpoint_manager=None):
        self.url = url
        self.project = project
        self.limit = limit
        self._checkpoint_manager = checkpoint_manager

    def get(self, es_query_set, start, params=None):
        import backoff

        @backoff.on_exception(
            backoff.expo, (ESError, ConnectionError),
            max_time=300, on_backoff=local_on_backoff, on_giveup=local_on_giveup,
        )
        def _inner(es_query_set, start, params):
            from commcare_export.cli import logger
            logger.info("Fetching batch: {}-{}".format(start, start + self.limit))
            return list(es_query_set[start:start + self.limit])

        return _inner(es_query_set, start, params)

    def iterate(self, resource, paginator, params=None):
        """
        Iterates through what the API would have been had it been passed in.
        """
        from commcare_export.cli import logger

        # resource is either 'form' or 'case'
        # params are api params
        # (e.g. {'limit': 1000, u'type': u'pregnant_mother', 'order_by': 'server_date_modified'})
        params = dict(params or {})
        mock_api = _get_mock_api(resource, self.project, params)

        def iterate_resource(resource=resource, params=params):
            more_to_fetch = True
            last_batch_ids = set()

            count = 0
            total_count = mock_api.query_set.count()
            while more_to_fetch:
                batch = self.get(mock_api.query_set, count, params)
                batch_list = [mock_api.serialize(obj) for obj in batch]
                logger.info('Received {}-{} of {}'.format(count, count + self.limit, total_count))

                if not batch_list:
                    more_to_fetch = False
                else:
                    for obj in batch_list:
                        if obj['id'] not in last_batch_ids:
                            yield obj

                    if count < total_count:
                        last_batch_ids = {obj['id'] for obj in batch_list}
                        count += self.limit
                    else:
                        more_to_fetch = False

                    self.checkpoint(paginator, batch_list)

        from commcare_export.repeatable_iterator import RepeatableIterator
        return RepeatableIterator(iterate_resource)

    def checkpoint(self, paginator, batch):
        from commcare_export.commcare_minilinq import DatePaginator
        if self._checkpoint_manager and isinstance(paginator, DatePaginator):
            since_date = paginator.get_since_date({"objects": batch})
            self._checkpoint_manager.set_batch_checkpoint(checkpoint_time=since_date)


class Command(BaseCommand):
    help = "For running commcare-export commands against a local environment. " \
           "This is mostly a once-off for the ICDS data team."

    def add_arguments(self, parser):
        parser.add_argument('--project')
        parser.add_argument('--query')
        parser.add_argument('--output-format')
        parser.add_argument('--output')
        parser.add_argument('--limit', type=int, default=200)

    def handle(self, project, query, output_format, output, limit, **options):
        # note: this is heavily copy/paste/modified from commcare_export.cli
        commcare_hq = 'local_commcare_export'
        try:
            # local development only
            sys.path.append(os.path.join(os.getcwd(), 'lib', 'commcare-export'))
            import commcare_export  # noqa
        except ImportError:
            raise CommandError(
                'This command requires commcare-export to be installed! '
                'Please run: pip install commcare-export. You may also need to run: '
                'pip install openpyxl==2.6.0b1 '
                'afterwards to run CommCare due to version incompatibilities.'
            )
        from commcare_export import misc
        from commcare_export.checkpoint import CheckpointManager
        from commcare_export.cli import _get_writer, _get_query_from_file
        from commcare_export.commcare_minilinq import CommCareHqEnv
        from commcare_export.env import BuiltInEnv, JsonPathEnv, EmitterEnv

        print('commcare-export is installed.')

        writer = _get_writer(output_format, output, strict_types=False)

        query_obj = _get_query_from_file(
            query,
            None,  # missing_value
            writer.supports_multi_table_write,
            writer.max_column_length,
            writer.required_columns
        )
        checkpoint_manager = None
        if writer.support_checkpoints:
            md5 = misc.digest_file(query)
            checkpoint_manager = CheckpointManager(
                output,
                query,
                md5,
                project,
                commcare_hq,
            )
            since = checkpoint_manager.get_time_of_last_checkpoint()

        else:
            since = None

        commcarehq_base_url = commcare_hq
        api_client = LocalCommCareHqClient(
            url=commcarehq_base_url,
            project=project,
            limit=limit,
            checkpoint_manager=checkpoint_manager
        )
        if since is not None:
            since = dateutil.parser.parse(since)

        env = (
            BuiltInEnv({'commcarehq_base_url': commcarehq_base_url})
            | CommCareHqEnv(api_client, since=since)
            | JsonPathEnv({})
            | EmitterEnv(writer)
        )

        with env:
            try:
                lazy_result = query_obj.eval(env)
                if lazy_result is not None:
                    # evaluate lazy results
                    for r in lazy_result:
                        list(r) if r else r
            except KeyboardInterrupt:
                print('\nExport aborted')
                return

        if checkpoint_manager:
            checkpoint_manager.set_final_checkpoint()
