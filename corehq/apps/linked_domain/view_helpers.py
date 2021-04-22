from django.db.models.expressions import RawSQL
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.fixtures.dbaccessors import (
    get_fixture_data_type_by_tag,
    get_fixture_data_types,
)
from corehq.apps.linked_domain.const import (
    LINKED_MODELS,
    MODEL_APP,
    MODEL_CASE_SEARCH,
    MODEL_DATA_DICTIONARY,
    MODEL_DIALER_SETTINGS,
    MODEL_FIXTURE,
    MODEL_HMAC_CALLOUT_SETTINGS,
    MODEL_KEYWORD,
    MODEL_OTP_SETTINGS,
    MODEL_REPORT,
)
from corehq.apps.linked_domain.models import (
    AppLinkDetail,
    DomainLinkHistory,
    FixtureLinkDetail,
    KeywordLinkDetail,
    ReportLinkDetail,
)
from corehq.apps.linked_domain.util import server_to_user_time
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.userreports.models import ReportConfiguration
from corehq.util.timezones.utils import get_timezone_for_request


def get_apps(domain):
    master_list = {}
    linked_list = {}
    briefs = get_brief_apps_in_domain(domain, include_remote=False)
    for brief in briefs:
        if is_linked_app(brief):
            linked_list[brief._id] = brief
        else:
            master_list[brief._id] = brief
    return master_list, linked_list


def get_fixtures(domain, master_link):
    master_list = get_fixtures_for_domain(domain)
    linked_list = get_fixtures_for_domain(master_link.master_domain) if master_link else {}
    return master_list, linked_list


def get_fixtures_for_domain(domain):
    fixtures = get_fixture_data_types(domain)
    return {f.tag: f for f in fixtures if f.is_global}


def get_reports(domain):
    master_list = {}
    linked_list = {}
    reports = get_report_configs_for_domain(domain)
    for report in reports:
        if report.report_meta.master_id:
            linked_list[report.get_id] = report
        else:
            master_list[report.get_id] = report
    return master_list, linked_list


def get_keywords(domain):
    master_list = {}
    linked_list = {}
    keywords = Keyword.objects.filter(domain=domain)
    for keyword in keywords:
        if keyword.upstream_id:
            linked_list[str(keyword.id)] = keyword
        else:
            master_list[str(keyword.id)] = keyword
    return master_list, linked_list


def build_app_view_models(apps):
    linked_models = dict(LINKED_MODELS)
    view_models = []
    for app in apps.values():
        view_model = build_view_model(
            model_type=MODEL_APP,
            name=f"{linked_models['app']} ({app.name})",
            detail=AppLinkDetail(app_id=app._id).to_json()
        )
        view_models.append(view_model)

    return view_models


def build_fixture_view_models(fixtures):
    linked_models = dict(LINKED_MODELS)
    view_models = []
    for fixture in fixtures.values():
        view_model = build_view_model(
            model_type=MODEL_FIXTURE,
            name=f"{linked_models['fixture']} ({fixture.tag})",
            detail=FixtureLinkDetail(tag=fixture.tag).to_json(),
            can_update=fixture.is_global
        )
        view_models.append(view_model)

    return view_models


def build_report_view_models(reports):
    linked_models = dict(LINKED_MODELS)
    view_models = []
    for report in reports.values():
        view_model = build_view_model(
            model_type=MODEL_REPORT,
            name=f"{linked_models['report']} ({report.title})",
            detail=ReportLinkDetail(report_id=report.get_id).to_json(),
        )
        view_models.append(view_model)

    return view_models


def build_keyword_view_models(keywords):
    linked_models = dict(LINKED_MODELS)
    view_models = []
    for keyword in keywords.values():
        view_model = build_view_model(
            model_type=MODEL_KEYWORD,
            name=f"{linked_models['keyword']} ({keyword.keyword})",
            detail=KeywordLinkDetail(keyword_id=str(keyword.id)).to_json(),
        )
        view_models.append(view_model)

    return view_models


def build_other_view_models(domain, ignore_models=None):
    ignore_models = ignore_models or []
    view_models = []

    for model, name in LINKED_MODELS:
        if (
            model not in ignore_models
            and model not in (MODEL_APP, MODEL_FIXTURE, MODEL_REPORT, MODEL_KEYWORD)
            and (model != MODEL_CASE_SEARCH or toggles.SYNC_SEARCH_CASE_CLAIM.enabled(domain))
            and (model != MODEL_DATA_DICTIONARY or toggles.DATA_DICTIONARY.enabled(domain))
            and (model != MODEL_DIALER_SETTINGS or toggles.WIDGET_DIALER.enabled(domain))
            and (model != MODEL_OTP_SETTINGS or toggles.GAEN_OTP_SERVER.enabled(domain))
            and (model != MODEL_HMAC_CALLOUT_SETTINGS or toggles.HMAC_CALLOUT.enabled(domain))
        ):
            view_models.append(
                build_view_model(
                    model_type=model,
                    name=name,
                    detail=None,
                    last_update=_('Never')
                )
            )

    return view_models


def build_view_model(model_type, name, detail, last_update=None, can_update=True):
    return {
        'type': model_type,
        'name': name,
        'detail': detail,
        'last_update': last_update,
        'can_update': can_update
    }


def get_master_model_status(domain, apps, fixtures, reports, keywords, ignore_models=None):
    """
    Models that originated in this domain
    In the context of linked domains, these are models used when "pushing" content
    :return:
    """
    view_models = []

    other_view_models = build_other_view_models(domain, ignore_models=ignore_models)
    view_models.extend(other_view_models)

    app_view_models = build_app_view_models(apps)
    view_models.extend(app_view_models)

    fixture_view_models = build_fixture_view_models(fixtures)
    view_models.extend(fixture_view_models)

    report_view_models = build_report_view_models(reports)
    view_models.extend(report_view_models)

    keyword_view_models = build_keyword_view_models(keywords)
    view_models.extend(keyword_view_models)

    return view_models


def get_model_status(domain, master_link, apps, fixtures, reports, keywords):
    """
    Models that originated in this domain's upstream domain
    In the context of linked domains, these are models used when "pulling" content
    """
    model_status = []
    if not master_link:
        return model_status

    models_seen = set()
    history = DomainLinkHistory.objects.filter(link=master_link).annotate(row_number=RawSQL(
        'row_number() OVER (PARTITION BY model, model_detail ORDER BY date DESC)',
        []
    ))
    linked_models = dict(LINKED_MODELS)
    timezone = get_timezone_for_request()
    for action in history:
        models_seen.add(action.model)
        if action.row_number != 1:
            # first row is the most recent
            continue
        name = linked_models[action.model]
        view_model = build_view_model(
            model_type=action.model,
            name=name,
            detail=action.model_detail,
            last_update=server_to_user_time(action.date, timezone)
        )
        if action.model == 'app':
            app_name = _('Unknown App')
            if action.model_detail:
                detail = action.wrapped_detail
                app = apps.pop(detail.app_id, None)
                app_name = app.name if app else detail.app_id
                if app:
                    view_model['detail'] = action.model_detail
                else:
                    view_model['can_update'] = False
            else:
                view_model['can_update'] = False
            view_model['name'] = '{} ({})'.format(name, app_name)

        if action.model == 'fixture':
            tag_name = _('Unknown Table')
            can_update = False
            if action.model_detail:
                tag = action.wrapped_detail.tag
                fixture = fixtures.pop(tag, None)
                if not fixture:
                    fixture = get_fixture_data_type_by_tag(domain, tag)
                if fixture:
                    tag_name = fixture.tag
                    can_update = fixture.is_global
            view_model['name'] = f'{name} ({tag_name})'
            view_model['can_update'] = can_update
        if action.model == 'report':
            report_id = action.wrapped_detail.report_id
            try:
                report = reports.get(report_id)
                del reports[report_id]
            except KeyError:
                report = ReportConfiguration.get(report_id)
            view_model['name'] = f'{name} ({report.title})'
        if action.model == 'keyword':
            keyword_id = action.wrapped_detail.linked_keyword_id
            try:
                keyword = keywords[keyword_id].keyword
                del keywords[keyword_id]
            except KeyError:
                try:
                    keyword = Keyword.objects.get(id=keyword_id).keyword
                except Keyword.DoesNotExist:
                    keyword = ugettext_lazy("Deleted Keyword")
                    view_model['can_update'] = False
            view_model['name'] = f'{name} ({keyword})'

        model_status.append(view_model)

    # Add in models and apps that have never been synced
    model_status.extend(
        get_master_model_status(
            domain, apps, fixtures, reports, keywords, ignore_models=models_seen)
    )

    return model_status
