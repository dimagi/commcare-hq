from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import six

from django_bulk_update.helper import bulk_update
from django.core.management import BaseCommand, CommandError
from corehq.warehouse.models.dimensions import ApplicationDim
from corehq.warehouse.models.facts import ApplicationStatusFact
from corehq.apps.es import FormES
from corehq.apps.es.aggregations import TermsAggregation, TopHitsAggregation
from corehq.util.queries import paginated_queryset
from dimagi.utils.chunked import chunked


def get_latest_build_ids(app_id, user_ids):
    query = (
        FormES()
        .domain('icds-cas')
        .app([app_id])
        .user_id(user_ids)
        .aggregation(
            TermsAggregation('user_id', 'form.meta.userID').aggregation(
                TopHitsAggregation(
                    'top_hits_last_form_submissions',
                    'form.meta.timeEnd',
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


def update_build_version_for_app(app_id):
    CHUNK_SIZE = 1000
    fact_chunks = chunked(
        paginated_queryset(
            ApplicationStatusFact.objects.filter(
                last_form_app_build_version__isnull=True,
                app_dim__application_id=app_id
            ).select_related('user_dim').all(),
            CHUNK_SIZE
        ),
        CHUNK_SIZE
    )

    version_by_build_id = {}

    def memoized_get_version(build_ids):
        new = set(build_ids) - set(six.iterkeys(version_by_build_id))
        if new:
            versions = ApplicationDim.objects.filter(
                application_id__in=new
            ).values_list('application_id', 'version')
            for k, v in versions:
                version_by_build_id[k] = v
        return {k: version_by_build_id[k] for k in build_ids}

    for fact_chunk in fact_chunks:
        facts_by_user_ids = {
            f.user_dim.user_id: f
            for f in fact_chunk
        }
        build_ids_by_user_ids = get_latest_build_ids(app_id, list(six.iterkeys(facts_by_user_ids)))
        build_ids = list(six.itervalues(build_ids_by_user_ids))
        # could have None value for some users
        build_ids.remove(None)
        version_by_build_id = memoized_get_version(build_ids)
        facts_to_update = []
        for user_id, fact in six.iteritems(facts_by_user_ids):
            build_id = build_ids_by_user_ids.get(user_id, '')
            version = version_by_build_id.get(build_id, '')
            if not fact.last_form_app_build_version and version:
                fact.last_form_app_build_version = version
                facts_to_update.append(fact)
        print("Updating {} facts for app {}".format(len(facts_to_update), app_id))
        bulk_update(facts_to_update)


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        app_ids = ApplicationDim.objects.filter(
            copy_of__isnull=True).values('application_id').distinct()
        )
        for app_id in six.itervalues(app_ids):
            update_build_version_for_app(app_id)
