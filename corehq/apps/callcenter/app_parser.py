from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple

from corehq.apps.callcenter import const
from corehq.apps.callcenter.models import CallCenterIndicatorConfig

ParsedIndicator = namedtuple('ParsedIndicator', 'category, type, date_range, is_legacy')


def get_call_center_config_from_app(app):
    indicators = get_indicators_used_in_app(app)
    custom_domain_indicators = const.PER_DOMAIN_FORM_INDICATORS.get(app.domain, {})
    parsed_indicators = [_f for _f in {
        parse_indicator(indicator, custom_domain_indicators) for indicator in indicators
    } if _f]
    config = CallCenterIndicatorConfig()
    for parsed_indicator in parsed_indicators:
        config.set_indicator(parsed_indicator)
    return config


def parse_indicator(indicator_name, custom_domain_indicators=None):
    custom_domain_indicators = custom_domain_indicators or {}
    is_legacy = '_' not in indicator_name
    if is_legacy:
        if indicator_name == const.LEGACY_TOTAL_CASES:
            return ParsedIndicator(const.CASES_TOTAL, None, None, True)

        for legacy_slug, new_slug in const.LEGACY_SLUG_MAP.items():
            if indicator_name.startswith(legacy_slug):
                period = indicator_name.lstrip(legacy_slug).lower()
                if period in const.DATE_RANGES:
                    return ParsedIndicator(new_slug, None, period, True)

        indicator_name_lower = indicator_name.lower()
        for date_range in const.DATE_RANGES:
            if indicator_name_lower.endswith(date_range):
                name = indicator_name[0:-len(date_range)]
                if name in custom_domain_indicators:
                    return ParsedIndicator(const.CUSTOM_FORM, name, date_range, False)

    else:
        split = indicator_name.rsplit('_')
        period = split[-1]
        slug = '{}_{}'.format(*split[0:2])
        type = None
        if len(split) == 4:
            type = split[-2]

        if period in const.DATE_RANGES and slug in const.STANDARD_SLUGS:
            return ParsedIndicator(slug, type, period, False)


def get_indicators_used_in_app(app):
    return _get_indicators_used_in_modules(app) | _get_indicators_used_in_forms(app)


def _get_indicators_used_in_modules(app):
    indicators = set()
    for module in app.get_modules():
        details = getattr(module, 'case_details', None)
        if details:
            indicators = indicators.union(_get_indicators_in_detail(details.short))
            indicators = indicators.union(_get_indicators_in_detail(details.long))

    return indicators


def _get_indicators_used_in_forms(app):
    indicators = set()
    for form in app.get_forms(bare=True):
        wrapped_form = form.wrapped_xform()
        if not wrapped_form.exists():
            continue

        instance_node = wrapped_form.model_node.find('{f}instance[@src="jr://fixture/indicators:call-center"]')
        if instance_node.exists():
            instance_id = instance_node.attrib['id']
            search_term = "instance('{}')".format(instance_id)
            for node in wrapped_form.model_node.xpath('*[contains(@calculate, "{}")]'.format(search_term)):
                xpath = node.attrib['calculate']
                indicator_name = xpath.split('/')[-1]
                indicators.add(indicator_name)

    return indicators


def _get_indicators_in_detail(detail):
    from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_INDICATOR
    for column in detail.columns:
        if FIELD_TYPE_INDICATOR == column.field_type:
            _, indicator = column.field_property.split('/', 1)
            yield indicator
