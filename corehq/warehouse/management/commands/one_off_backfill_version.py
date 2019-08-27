from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import six

from django_bulk_update.helper import bulk_update
from django.core.management import BaseCommand
from corehq.warehouse.models.dimensions import ApplicationDim
from corehq.warehouse.models.facts import ApplicationStatusFact
from corehq.apps.es import FormES
from corehq.apps.es.aggregations import TermsAggregation, TopHitsAggregation
from corehq.util.queries import paginated_queryset
from dimagi.utils.chunked import chunked
from corehq.elastic import ES_EXPORT_INSTANCE


def get_latest_build_ids(domain, app_id, user_ids):
    query = (
        FormES(es_instance_alias=ES_EXPORT_INSTANCE)
        .domain(domain)
        .app([app_id])
        .user_id(user_ids)
        .aggregation(
            TermsAggregation('user_id', 'form.meta.userID').aggregation(
                TopHitsAggregation(
                    'top_hits_last_form_submissions',
                    'received_on',
                    is_ascending=False,
                    include=['build_id'],
                )
            )
        )
        .size(0)
    )
    aggregations = query.run().aggregations
    buckets_dict = aggregations.user_id.buckets_dict
    result = {}
    for user_id, bucket in six.iteritems(buckets_dict):
        result[user_id] = bucket.top_hits_last_form_submissions.hits[0]['build_id']
    return result


def update_build_version_for_app(domain, app_id, check_only):
    CHUNK_SIZE = 1000
    fact_chunks = chunked(
        paginated_queryset(
            ApplicationStatusFact.objects.filter(
                domain=domain,
                last_form_app_build_version__isnull=True,
                app_dim__application_id=app_id
            ).select_related('user_dim').all(),
            CHUNK_SIZE
        ),
        CHUNK_SIZE
    )

    version_by_build_id = {}

    def memoized_get_versions(build_ids):
        new = set(build_ids) - set(six.iterkeys(version_by_build_id))
        if new:
            versions = ApplicationDim.objects.filter(
                domain=domain,
                application_id__in=new
            ).values_list('application_id', 'version')
            for k, v in versions:
                version_by_build_id[k] = v
        return {k: version_by_build_id[k] for k in build_ids if k in version_by_build_id}

    for fact_chunk in fact_chunks:
        facts_by_user_ids = {
            f.user_dim.user_id: f
            for f in fact_chunk
        }
        build_ids_by_user_ids = get_latest_build_ids(domain, app_id, list(six.iterkeys(facts_by_user_ids)))
        build_ids = list(six.itervalues(build_ids_by_user_ids))
        version_by_build_id = memoized_get_versions(build_ids)
        facts_to_update = []
        for user_id, fact in six.iteritems(facts_by_user_ids):
            build_id = build_ids_by_user_ids.get(user_id, '')
            version = version_by_build_id.get(build_id, '')
            if not fact.last_form_app_build_version and version:
                fact.last_form_app_build_version = version
                facts_to_update.append(fact)
        if check_only:
            for fact in facts_to_update:
                print("Fact ID {}, user {}, version {}".format(
                    fact.id, fact.user_dim.user_id, fact.last_form_app_build_version))
        else:
            print("Updating {} facts for app {}".format(len(facts_to_update), app_id))
            bulk_update(facts_to_update)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--check_only',
            action='store_true',
            dest='check_only',
            default=True,
            help="Dry Run and print results"
        )

    def handle(self, domain, **options):
        app_ids = ApplicationDim.objects.filter(
            domain=domain,
            copy_of__isnull=True
        ).values_list('application_id', flat=True).distinct()
        for app_id in app_ids:
            update_build_version_for_app(domain, app_id, options['check_only'])
