from __future__ import absolute_import, division

from __future__ import unicode_literals
import json
from collections import OrderedDict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic.base import View

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from custom.champ.sqldata import TargetsDataSource, UICFromEPMDataSource, UICFromCCDataSource, \
    HivStatusDataSource, FormCompletionDataSource, FirstArtDataSource, LastVLTestDataSource, \
    ChampFilter
from custom.champ.utils import PREVENTION_XMLNS, POST_TEST_XMLNS, ACCOMPAGNEMENT_XMLNS, \
    SUIVI_MEDICAL_XMLNS, ENHANCED_PEER_MOBILIZATION, CHAMP_CAMEROON, TARGET_XMLNS


def get_user_ids_for_group(groups):
    users = []
    for group_id in groups:
        group = Group.get(group_id)
        users.extend(group.get_user_ids())
    return users


def get_age_ranges(ages):
    ranges = []
    for age in ages:
        if age != '50+ yrs' and age != '':
            start_end = age.split(" ")[0].split("-")
            ranges.append({'start': start_end[0], 'end': start_end[1]})
        elif age == '50+ yrs':
            ranges.append({'start': 50, 'end': 200})
    return ranges


def update_date_property(config, post_data, property, filter_key):
    value = post_data.get(property, '')
    if value:
        start_key = '%s_start' % filter_key
        end_key = '%s_end' % filter_key
        start, end = value.split(' - ')
        config.update({
            start_key: start,
            end_key: end
        })


class ChampView(View):
    @property
    def post_data(self):
        return json.loads(self.request.body.decode('utf-8'))

    def get_list_property(self, property):
        value = self.post_data.get(property, [])
        return [] if '' in value else value


@method_decorator([login_and_domain_required], name='dispatch')
class PrevisionVsAchievementsView(ChampView):
    def get_target_data(self, domain):
        config = {
            'domain': domain,
            'district': self.get_list_property('target_district'),
            'cbo': self.get_list_property('target_cbo'),
            'userpl': self.get_list_property('target_userpl'),
            'fiscal_year': self.post_data.get('target_fiscal_year', None)
        }

        clienttype = self.get_list_property('target_clienttype')
        for idx, type in enumerate(clienttype):
            if type == 'client_fsw':
                type = 'cfsw'
            clienttype[idx] = type.lower()

        config.update({'clienttype': clienttype})
        target_data = TargetsDataSource(config=config).data
        return target_data

    def get_kp_prev_achievement(self, domain):
        config = {
            'domain': domain,
            'age': get_age_ranges(self.get_list_property('kp_prev_age')),
            'district': self.get_list_property('kp_prev_district'),
            'activity_type': self.post_data.get('kp_prev_activity_type', None),
            'type_visit': self.post_data.get('kp_prev_visit_type', None),
            'client_type': self.get_list_property('kp_prev_client_type'),
            'user_id': get_user_ids_for_group(self.get_list_property('kp_prev_user_group')),
            'want_hiv_test': self.post_data.get('kp_prev_want_hiv_test', None),
        }
        update_date_property(config, self.post_data, 'kp_prev_visit_date', 'visit_date')

        achievement = UICFromEPMDataSource(config=config).data
        return achievement.get(PREVENTION_XMLNS, {}).get('uic', 0)

    def get_htc_tst_achievement(self, domain):
        config = {
            'domain': domain,
            'age_range': self.get_list_property('htc_tst_age_range'),
            'district': self.get_list_property('htc_tst_district'),
            'client_type': self.get_list_property('htc_tst_client_type'),
            'user_id': get_user_ids_for_group(self.get_list_property('htc_tst_user_group')),
        }
        update_date_property(config, self.post_data, 'htc_tst_post_date', 'posttest_date')
        update_date_property(config, self.post_data, 'htc_tst_hiv_test_date', 'hiv_test_date')
        achievement = UICFromCCDataSource(config=config).data
        return achievement.get(POST_TEST_XMLNS, {}).get('uic', 0)

    def get_htc_pos_achievement(self, domain):
        config = {
            'domain': domain,
            'age_range': self.get_list_property('htc_pos_age_range'),
            'district': self.get_list_property('htc_pos_district'),
            'client_type': self.get_list_property('htc_pos_client_type'),
            'user_id': get_user_ids_for_group(self.get_list_property('htc_pos_user_group')),
        }
        update_date_property(config, self.post_data, 'htc_pos_post_date', 'posttest_date')
        update_date_property(config, self.post_data, 'htc_pos_hiv_test_date', 'hiv_test_date')
        achievement = HivStatusDataSource(config=config).data
        return achievement.get(POST_TEST_XMLNS, {}).get('uic', 0)

    def get_care_new_achivement(self, domain):
        config = {
            'domain': domain,
            'hiv_status': self.get_list_property('care_new_hiv_status'),
            'client_type': self.get_list_property('care_new_client_type'),
            'age_range': self.get_list_property('care_new_age_range'),
            'district': self.get_list_property('care_new_district'),
            'user_id': get_user_ids_for_group(self.get_list_property('care_new_user_group')),
        }
        update_date_property(config, self.post_data, 'care_new_date_handshake', 'date_handshake')
        achievement = FormCompletionDataSource(config=config).data
        return achievement.get(ACCOMPAGNEMENT_XMLNS, {}).get('uic', 0)

    def get_tx_new_achivement(self, domain):
        config = {
            'domain': domain,
            'hiv_status': self.get_list_property('tx_new_hiv_status'),
            'client_type': self.get_list_property('tx_new_client_type'),
            'age_range': self.get_list_property('tx_new_age_range'),
            'district': self.get_list_property('tx_new_district'),
            'user_id': get_user_ids_for_group(self.get_list_property('tx_new_user_group')),
        }
        update_date_property(config, self.post_data, 'tx_new_first_art_date', 'first_art_date')
        achievement = FirstArtDataSource(config=config).data
        return achievement.get(SUIVI_MEDICAL_XMLNS, {}).get('uic', 0)

    def get_tx_undetect_achivement(self, domain):
        config = {
            'domain': domain,
            'hiv_status': self.get_list_property('tx_undetect_hiv_status'),
            'client_type': self.get_list_property('tx_undetect_client_type'),
            'age_range': self.get_list_property('tx_undetect_age_range'),
            'district': self.get_list_property('tx_undetect_district'),
            'undetect_vl': self.post_data.get('tx_undetect_undetect_vl', None),
            'user_id': get_user_ids_for_group(self.get_list_property('tx_undetect_user_group')),
        }
        update_date_property(config, self.post_data, 'tx_undetect_date_last_vl_test', 'date_last_vl_test')
        achievement = LastVLTestDataSource(config=config).data
        return achievement.get(SUIVI_MEDICAL_XMLNS, {}).get('uic', 0)

    def generate_data(self, domain):
        targets = self.get_target_data(domain)
        return {
            'chart': [
                {
                    'key': 'Target',
                    'color': 'blue',
                    'values': [
                        {'x': 'KP_PREV', 'y': (targets.get('target_kp_prev', 0) or 0)},
                        {'x': 'HTC_TST', 'y': (targets.get('target_htc_tst', 0) or 0)},
                        {'x': 'HTC_POS', 'y': (targets.get('target_htc_pos', 0) or 0)},
                        {'x': 'CARE_NEW', 'y': (targets.get('target_care_new', 0) or 0)},
                        {'x': 'TX_NEW', 'y': (targets.get('target_tx_new', 0) or 0)},
                        {'x': 'TX_UNDETECT', 'y': (targets.get('target_tx_undetect', 0) or 0)}
                    ]
                },
                {
                    'key': 'Achievements',
                    'color': 'orange',
                    'values': [
                        {'x': 'KP_PREV', 'y': self.get_kp_prev_achievement(domain)},
                        {'x': 'HTC_TST', 'y': self.get_htc_tst_achievement(domain)},
                        {'x': 'HTC_POS', 'y': self.get_htc_pos_achievement(domain)},
                        {'x': 'CARE_NEW', 'y': self.get_care_new_achivement(domain)},
                        {'x': 'TX_NEW', 'y': self.get_tx_new_achivement(domain)},
                        {'x': 'TX_UNDETECT', 'y': self.get_tx_undetect_achivement(domain)}
                    ]
                }
            ]
        }

    def post(self, request, *args, **kwargs):
        domain = self.kwargs['domain']
        return JsonResponse(data=self.generate_data(domain))


@method_decorator([login_and_domain_required], name='dispatch')
class PrevisionVsAchievementsTableView(ChampView):

    def generate_data(self, domain):
        config = {
            'domain': domain,
            'district': self.get_list_property('district'),
            'cbo': self.get_list_property('cbo'),
            'type_visit': self.post_data.get('visit_type', None),
            'activity_type': self.post_data.get('activity_type', None),
            'client_type': self.get_list_property('client_type'),
            'user_id': get_user_ids_for_group(self.get_list_property('organization')),
            'fiscal_year': self.post_data.get('fiscal_year', None),
        }

        update_date_property(config, self.post_data, 'visit_date', 'visit_date')
        update_date_property(config, self.post_data, 'posttest_date', 'posttest_date')
        update_date_property(config, self.post_data, 'first_art_date', 'first_art_date')
        update_date_property(config, self.post_data, 'date_handshake', 'date_handshake')
        update_date_property(config, self.post_data, 'date_last_vl_test', 'date_last_vl_test')

        target_client_types = []
        for client_type in config['client_type']:
            if client_type == 'client_fsw':
                client_type = 'cfsw'
            target_client_types.append(client_type.lower())
        config.update({'clienttype': target_client_types})
        targets = TargetsDataSource(config=config.copy()).data
        kp_prev = UICFromEPMDataSource(config=config.copy()).data
        htc_tst = UICFromCCDataSource(config=config.copy()).data
        htc_pos = HivStatusDataSource(config=config.copy()).data
        care_new = FormCompletionDataSource(config=config.copy()).data
        tx_new = FirstArtDataSource(config=config.copy()).data
        tz_undetect = LastVLTestDataSource(config=config).data

        return {
            'target_kp_prev': (targets.get('target_kp_prev', 0) or 0),
            'target_htc_tst': (targets.get('target_htc_tst', 0) or 0),
            'target_htc_pos': (targets.get('target_htc_pos', 0) or 0),
            'target_care_new': (targets.get('target_care_new', 0) or 0),
            'target_tx_new': (targets.get('target_tx_new', 0) or 0),
            'target_tx_undetect': (targets.get('target_tx_undetect', 0) or 0),
            'kp_prev': (kp_prev.get(PREVENTION_XMLNS, {}).get('uic', 0) or 0),
            'htc_tst': (htc_tst.get(POST_TEST_XMLNS, {}).get('uic', 0) or 0),
            'htc_pos': (htc_pos.get(POST_TEST_XMLNS, {}).get('uic', 0) or 0),
            'care_new': (care_new.get(ACCOMPAGNEMENT_XMLNS, {}).get('uic', 0) or 0),
            'tx_new': (tx_new.get(SUIVI_MEDICAL_XMLNS, {}).get('uic', 0) or 0),
            'tx_undetect': (tz_undetect.get(SUIVI_MEDICAL_XMLNS, {}).get('uic', 0) or 0),
        }

    def post(self, request, *args, **kwargs):
        domain = self.kwargs['domain']
        return JsonResponse(data=self.generate_data(domain))


@method_decorator([login_and_domain_required], name='dispatch')
class ServiceUptakeView(ChampView):

    def generate_data(self, domain):
        month_start = self.post_data.get('month_start', 1)
        year_start = self.post_data.get('year_start', datetime.now().year)
        month_end = self.post_data.get('month_end', datetime.now().month)
        year_end = self.post_data.get('year_end', datetime.now().year)

        start_date = datetime(year_start, month_start, 1)
        end_date = (datetime(year_end, month_end, 1) + relativedelta(months=1)) - relativedelta(days=1)

        config = {
            'domain': domain,
            'district': self.get_list_property('district'),
            'type_visit': self.post_data.get('visit_type', None),
            'activity_type': self.post_data.get('activity_type', None),
            'client_type': self.get_list_property('client_type'),
            'user_id': get_user_ids_for_group(self.get_list_property('organization')),
            'visit_date_start': start_date,
            'visit_date_end': end_date,
            'posttest_date_start': start_date,
            'posttest_date_end': end_date,
            'date_handshake_start': start_date,
            'date_handshake_end': end_date,
        }

        kp_prev = UICFromEPMDataSource(config=config.copy(), replace_group_by='kp_prev_month').data
        htc_tst = UICFromCCDataSource(config=config.copy(), replace_group_by='htc_month').data
        htc_pos = HivStatusDataSource(config=config.copy(), replace_group_by='htc_month').data
        care_new = FormCompletionDataSource(config=config, replace_group_by='care_new_month').data

        htc_uptake_chart_data = OrderedDict()
        htc_yield_chart_data = OrderedDict()
        link_chart_data = OrderedDict()

        rrule_dates = [
            rrule_date for rrule_date in rrule(
                MONTHLY,
                dtstart=start_date,
                until=end_date
            )
        ]
        tickValues = []
        for rrule_dt in rrule_dates:
            date_in_milliseconds = int(rrule_dt.date().strftime("%s")) * 1000
            tickValues.append(date_in_milliseconds)
            htc_uptake_chart_data.update({date_in_milliseconds: 0})
            htc_yield_chart_data.update({date_in_milliseconds: 0})
            link_chart_data.update({date_in_milliseconds: 0})

        for row in htc_tst.values():
            date = row['htc_month']
            date_in_milliseconds = int(date.strftime("%s")) * 1000
            nom = (row['uic'] or 0)
            denom = (kp_prev[date]['uic'] or 1) if date in kp_prev else 1
            htc_uptake_chart_data[date_in_milliseconds] = nom / denom

        for row in htc_pos.values():
            date = row['htc_month']
            date_in_milliseconds = int(date.strftime("%s")) * 1000
            nom = (row['uic'] or 0)
            denom = (htc_tst[date]['uic'] or 1) if date in htc_tst else 1
            htc_yield_chart_data[date_in_milliseconds] = nom / denom

        for row in care_new.values():
            date = row['care_new_month']
            date_in_milliseconds = int(date.strftime("%s")) * 1000
            nom = (row['uic'] or 0)
            denom = (htc_pos[date]['uic'] or 1) if date in htc_pos else 1
            link_chart_data[date_in_milliseconds] = nom / denom

        return {
            'chart': [
                {
                    "values": [
                        {'x': key, 'y': value} for key, value in htc_uptake_chart_data.items()
                    ],
                    "key": "HTC_uptake",
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": "blue"
                },
                {
                    "values": [
                        {'x': key, 'y': value} for key, value in htc_yield_chart_data.items()
                    ],
                    "key": "HTC_yield",
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": "orange"
                },
                {
                    "values": [
                        {'x': key, 'y': value} for key, value in link_chart_data.items()
                    ],
                    "key": "Link to care",
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": "gray"
                }
            ],
            'tickValues': tickValues
        }

    def post(self, request, *args, **kwargs):
        domain = self.kwargs['domain']
        return JsonResponse(data=self.generate_data(domain))


@method_decorator([login_and_domain_required], name='dispatch')
class ChampFilterView(View):
    xmlns = None
    table_name = None
    column_name = None

    def get(self, request, *args, **kwargs):
        domain = self.kwargs['domain']
        return JsonResponse(data={
            'options': ChampFilter(domain, self.xmlns, self.table_name, self.column_name).data
        })


class PreventionPropertiesFilter(ChampFilterView):
    xmlns = PREVENTION_XMLNS
    table_name = ENHANCED_PEER_MOBILIZATION


class PostTestFilter(ChampFilterView):
    xmlns = POST_TEST_XMLNS
    table_name = CHAMP_CAMEROON


class TargetFilter(ChampFilterView):
    xmlns = TARGET_XMLNS
    table_name = ENHANCED_PEER_MOBILIZATION


class DistrictFilterPrevView(PreventionPropertiesFilter):
    column_name = 'district'


class CBOFilterView(TargetFilter):
    column_name = 'cbo'


class UserPLFilterView(TargetFilter):
    column_name = 'userpl'


class UserGroupsFilter(View):
    def get(self, request, *args, **kwargs):
        domain = self.kwargs['domain']
        groups = Group.by_domain(domain)
        options = [{'id': '', 'text': 'All'}]
        return JsonResponse(data={
            'options': options + [{'id': group.get_id, 'text': group.name} for group in groups]
        })


class OrganizationsFilter(View):
    def get(self, request, *args, **kwargs):
        domain = self.kwargs['domain']
        locations = SQLLocation.objects.filter(domain=domain).exclude(location_type__code='dic')
        options = [{'id': '', 'value': 'All'}]
        return JsonResponse(data={
            'options': options + [{'id': loc.location_id, 'value': loc.name} for loc in locations]
        })


class HierarchyFilter(View):
    def get(self, request, *args, **kwargs):
        domain = self.kwargs['domain']
        districts = FixtureDataItem.get_item_list(domain, 'district')
        cbos = FixtureDataItem.get_item_list(domain, 'cbo')
        clienttypes = FixtureDataItem.get_item_list(domain, 'clienttype')
        userpls = FixtureDataItem.get_item_list(domain, 'userpl')

        def to_filter_format(data, parent_key=None):
            locations = [dict(
                id='',
                text='All'
            )]
            for row in data:
                loc_id = row.fields['id'].field_list[0].field_value
                loc = dict(
                    id=loc_id,
                    text=loc_id
                )
                if parent_key:
                    parent_id = row.fields[parent_key].field_list[0].field_value
                    loc.update({'parent_id': parent_id})
                locations.append(loc)
            return locations

        hierarchy = {
            'districts': to_filter_format(districts),
            'cbos': to_filter_format(cbos, 'district_id'),
            'clienttypes': to_filter_format(clienttypes, 'cbo_id'),
            'userpls': to_filter_format(userpls, 'clienttype_id')
        }
        return JsonResponse(data=hierarchy)
