import datetime

from corehq.apps.es import AppES, FormES
from corehq.apps.es.aggregations import TermsAggregation
from corehq.apps.experiments import ES_FOR_EXPORTS, Experiment
from corehq.const import MISSING_APP_ID
from corehq.util.couch import stale_ok
from corehq.util.dates import iso_string_to_datetime
from corehq.util.quickcache import quickcache

experiment = Experiment(
    campaign=ES_FOR_EXPORTS,
    old_args={},
    new_args={'use_es': True},
    is_equal=lambda a, b: True,
)


@quickcache(['domain'], timeout=10 * 60)
def domain_has_submission_in_last_30_days(domain):
    thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    return (FormES()
            .domain(domain)
            .submitted(gte=thirty_days_ago)
            .exists())


def get_number_of_forms_in_domain(domain):
    return FormES().domain(domain).count()


def _received_on_query(domain, desc=False):
    return (
        FormES()
        .fields(['received_on'])
        .domain(domain)
        .sort('received_on', desc=desc)
    )


def get_first_form_submission_received(domain):
    result = _received_on_query(domain)[0]

    if not result:
        return

    return iso_string_to_datetime(result[0]['received_on'])


def get_last_form_submission_received(domain):
    result = _received_on_query(domain, desc=True)[0]

    if not result:
        return

    return iso_string_to_datetime(result[0]['received_on'])


@quickcache(['domain'], memoize_timeout=0, timeout=12 * 3600)
def get_all_xmlns_app_id_pairs_submitted_to_in_domain(domain):
    """This is used to get (XMLNS, app_id) from submitted forms. The results
    get combined with data from all current app versions which means
    that this is only used to get (XMLNS, app_id) combos from forms submitted
    in the past which no longer have a corresponding form in the app (e.g. form deleted)

    Given that we can cache this for a long period of time under the assumption that
    a user isn't going to submit a form and then delete it from their app immediately.
    """
    query = (FormES()
             .domain(domain)
             .aggregation(
                 TermsAggregation("app_id", "app_id", missing=MISSING_APP_ID).aggregation(
                     TermsAggregation("xmlns", "xmlns.exact")))
             .remove_default_filter("has_xmlns")
             .remove_default_filter("has_user")
             .size(0))
    query_result = query.run()
    form_counts = set()
    for app_id, bucket in query_result.aggregations.app_id.buckets_dict.items():
        for sub_bucket in bucket.xmlns.buckets_list:
            xmlns = sub_bucket.key
            form_counts.add((xmlns, app_id))
    return form_counts


@quickcache(['domain', 'app_id', 'xmlns'], memoize_timeout=0, timeout=5 * 60)
def get_form_analytics_metadata(domain, app_id, xmlns):
    """
    Returns metadata about the form, or None if no info found.

    Here is an example structure:
    {
        "xmlns": "http://openrosa.org/formdesigner/5D563904-4038-4070-A0D4-CC421003E862",
        "form": {
            "name": {
                "en": "Brogramming Project",
                "es": "Projecto de brogramming"
            },
            "id": 1
        },
        "app": {
            "langs": [
                "es",
                "en",
                "fra"
            ],
            "name": "brogrammino",
            "id": "10257bd886ba423eea19a562e95cec07"
        },
        "module": {
            "name": {
                "en": "Dimagi",
                "es": "Brogramminos"
            },
            "id": 0
        },
        "app_deleted": false,
        "submissions": 15
    }
    """
    # todo: wrap this return value in a class/stucture
    from corehq.apps.app_manager.models import Application
    view_results = Application.get_db().view(
        'exports_forms_by_app/view',
        key=[domain, app_id, xmlns],
        stale=stale_ok(),
        group=True
    ).one()
    form_counts = get_form_count_breakdown_for_domain(domain)
    form_count = form_counts.get((domain, app_id, xmlns))
    if view_results:
        result = view_results['value']
        result['submissions'] = form_count
        return result
    elif form_count:
        return {'xmlns': xmlns, 'submissions': form_count}
    else:
        return None


def get_exports_by_form(domain, use_es=False):
    if use_es:
        # if use_es is True here, the "export_apps_use_elasticsearch" ff is enabled for
        # this domain so just return es results without the experiment
        rows = _get_export_forms_by_app_es(domain)
    else:
        rows = _experiment_get_export_forms(domain)
    form_count_breakdown = get_form_count_breakdown_for_domain(domain)

    for row in rows:
        key = tuple(row['key'])
        if key in form_count_breakdown:
            row['value']['submissions'] = form_count_breakdown.pop(key)

    for key, value in form_count_breakdown.items():
        rows.append({'key': list(key), 'value': {'xmlns': key[2], 'submissions': value}})

    rows.sort(key=lambda row: row['key'])
    return rows


@experiment
def _experiment_get_export_forms(domain, use_es=False):
    from corehq.apps.app_manager.models import Application
    if use_es:
        rows = _get_export_forms_by_app_es(domain)
    else:
        rows = Application.get_db().view(
            'exports_forms_by_app/view',
            startkey=[domain],
            endkey=[domain, {}],
            group=True,
            stale=stale_ok()
        ).all()
    return rows


def _get_export_forms_by_app_es(domain):
    rows = []
    apps = AppES().domain(domain).is_build(False).run().hits
    for app in apps:
        for module_id, module in enumerate(app.get("modules", [])):
            for form_id, form in enumerate(module.get("forms", [])):
                rows.append({
                    "key": [app['domain'], app['_id'], form["xmlns"]],
                    "value": {
                        "xmlns": form["xmlns"],
                        "app": {"name": app["name"], "langs": app["langs"], "id": app["_id"]},
                        "module": {"name": module["name"], "id": module_id},
                        "form": {"name": form["name"], "id": form_id},
                        "app_deleted": app["doc_type"] in ["Application-Deleted", "LinkedApplication-Deleted"],
                    }
                })

    return rows


def get_form_count_breakdown_for_domain(domain):
    query = (FormES(for_export=True)
             .domain(domain)
             .aggregation(
                 TermsAggregation("app_id", "app_id").aggregation(
                     TermsAggregation("xmlns", "xmlns.exact")))
             .remove_default_filter("has_xmlns")
             .remove_default_filter("has_user")
             .size(0))
    query_result = query.run()
    form_counts = {}
    for app_id, bucket in query_result.aggregations.app_id.buckets_dict.items():
        for sub_bucket in bucket.xmlns.buckets_list:
            xmlns = sub_bucket.key
            form_counts[(domain, app_id, xmlns)] = sub_bucket.doc_count
    return form_counts
