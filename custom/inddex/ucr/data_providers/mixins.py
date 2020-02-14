from abc import abstractmethod

from memoized import memoized
from sqlagg.columns import SimpleColumn
from sqlagg.filters import GTE, LTE, EQ

from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.inddex.couch_db_data_collector import CouchDbDataCollector
from custom.inddex.sqldata import FoodConsumptionDataSourceMixin


def get_slugs(slugs, config):
    filters = []
    for slug in slugs:
        if config.get(slug):
            filters.append(EQ(slug, slug))

    return filters


class ReportDataMixin(FoodConsumptionDataSourceMixin):
    title = None
    table_names = []
    headers_in_order = []
    TABLE_NAMES = [
        'doc_id', 'inserted_at', 'recall_case_id', 'owner_name', 'opened_by_username', 'recall_status',
        'unique_respondent_id', 'gender', 'age', 'supplements', 'urban_rural', 'pregnant', 'breastfeeding',
        'food_code', 'reference_food_code', 'food_type', 'include_in_analysis', 'food_status', 'recall_date',
        'opened_date', 'eating_time', 'time_block', 'already_reported_food', 'already_reported_food_caseid',
        'is_ingredient', 'ingr_recipe_case_id', 'ingr_recipe_code', 'short_name', 'food_name', 'recipe_name',
        'food_base_term', 'tag_1', 'other_tag_1', 'tag_2', 'other_tag_2', 'tag_3', 'other_tag_3', 'tag_4',
        'other_tag_4', 'tag_5', 'other_tag_5', 'tag_6', 'other_tag_6', 'tag_7', 'other_tag_7', 'tag_8',
        'other_tag_8', 'tag_9', 'other_tag_9', 'tag_10', 'other_tag_10', 'conv_method', 'conv_method_desc',
        'conv_option', 'conv_option_desc', 'conv_size', 'conv_units', 'quantity',
        'nsr_conv_method_code_post_cooking', 'nsr_conv_option_code_post_cooking',
        'nsr_conv_option_desc_post_cooking', 'nsr_conv_size_post_cooking', 'nsr_same_conv_method',
        'respondent_id', 'recipe_case_id'
    ]
    id_field = 'doc_id'
    couch_db = None

    @property
    def obligatory_table_names(self):
        return [
            self.id_field, 'food_code', 'food_type', 'food_base_term',
            'conv_method', 'conv_option', 'reference_food_code', 'age'
        ]

    @property
    def obligatory_couch_names(self):
        return [
            'conv_factor_gap_code', 'fct_gap_code', 'conv_factor_gap_desc', 'fct_gap_desc',
            'conv_factor_food_code', 'conv_factor_used'
        ]

    @property
    def filters(self):
        filters = [GTE('recall_date', 'startdate'), LTE('recall_date', 'enddate')]
        if self.config['case_owners']:
            filters.append(EQ('owner_name', 'case_owners'))
        if self.config['recall_status']:
            filters.append(EQ('recall_status', 'recall_status'))

        return filters

    @property
    def additional_filters(self):
        return {}

    @property
    def headers(self):
        return [DataTablesColumn(header) for header in self.headers_in_order]

    @property
    def columns(self):
        return [
            DatabaseColumn(header, SimpleColumn(header))
            for header in set(self.headers_in_order + self.obligatory_table_names)
            if header in self.TABLE_NAMES
        ]

    @property
    def group_by(self):
        return [
            header
            for header in set(self.headers_in_order + self.obligatory_table_names)
            if header in self.TABLE_NAMES
        ]

    @property
    @memoized
    def rows(self):
        return self._get_raw_data()

    def rearrange_data(self, rows):
        result = []
        for row in rows:
            record = []
            for header in self.headers_in_order:
                if header == self.id_field:
                    record.append(row['id'])
                else:
                    record.append(row['data'][header])
            result.append(record)

        return result

    def append_fao_who_information(self, data):
        fields_and_values = (
            ('food_code', tuple(record['data']['food_code'] for record in data if record['data']['food_code'])),
        )
        records_dict = self.couch_db.get_data_from_table_as_dict(
            table_name='food_composition_table', key_field='food_code', fields_and_values=fields_and_values
        )

        for record in data:
            food_code = record['data']['food_code']
            if food_code in records_dict:
                record['data']['fao_who_gift_food_group_code'] = \
                    records_dict[food_code]['fao_who_gift_food_group_code']
                record['data']['fao_who_gift_food_group_description'] = \
                    records_dict[food_code]['fao_who_gift_food_group_description']

    def _get_raw_data(self):
        raw_data = []
        for data in self.get_data():
            id_ = data[self.id_field]
            tmp = data.copy()
            tmp.pop(self.id_field)
            for name in set(self.obligatory_couch_names + self.headers_in_order):
                if name not in self.group_by:
                    tmp[name] = None
            raw_data.append({'id': id_, 'data': tmp})

        return raw_data


class AdditionalDataMixin:
    couch_db = None

    def append_fct_gap_information(self, data):
        food_items, std_recipes, non_food_items, non_std_recipes = self._rearrange_data_for_gap_calculations(data)

        def _append_gap_code_three():
            fields_and_values = (
                ('food_code', tuple(record['data']['reference_food_code'] for record in food_items)),
            )
            _, conv_codes = self._get_filtered_data('food_composition_table', fields_and_values)
            for record in food_items.copy():
                if record['data']['reference_food_code'] in conv_codes:
                    food_items.pop(food_items.index(record))
                    self._set_gap_code_and_description(
                        record['data'], '3', 'using fct data from reference food code'
                    )
                    self._set_fct_food_information(record['data'], 'reference_food_code')

        def _append_gap_code_seven():
            recipes_codes = [
                record['data']['food_code']
                for record in std_recipes+non_std_recipes
                if record['data']['food_code']
            ]
            fields_and_values = (('recipe_code', tuple(recipes_codes)),)
            recipes_with_ingredients = {}
            for element in self.couch_db.get_data_from_table(
                table_name='recipes', fields_and_values=fields_and_values
            ):
                element_dict = self.couch_db.record_to_dict(element)
                if not recipes_with_ingredients.get(element_dict['ingr_code']):
                    recipes_with_ingredients[element_dict['ingr_code']] = {element_dict['recipe_code']}
                else:
                    recipes_with_ingredients[element_dict['ingr_code']].add(element_dict['recipe_code'])
            fields_and_values = (('food_code', tuple(key for key in recipes_with_ingredients)),)

            def _append(_fields_and_values):
                conv_data, conv_codes = self._get_filtered_data('food_composition_table', _fields_and_values)
                keys = set()
                for key in recipes_with_ingredients:
                    if key in conv_codes:
                        for recipe_code in recipes_with_ingredients[key]:
                            keys.add(recipe_code)

                for record in std_recipes.copy() + non_std_recipes.copy():
                    if record['data']['food_code'] in keys:
                        if record in std_recipes:
                            std_recipes.pop(std_recipes.index(record))
                        else:
                            non_std_recipes.pop(non_std_recipes.index(record))
                        self._set_gap_code_and_description(
                            record['data'], '7', 'ingredient(s) contain fct data gaps'
                        )

            def _append_for_gap_code_two():
                recipes_with_base_terms = {}
                for record in self.couch_db.get_data_from_table(
                    table_name='food_list', fields_and_values=fields_and_values
                ):
                    record_dict = self.couch_db.record_to_dict(record)
                    if not recipes_with_base_terms.get(record_dict['food_code']):
                        recipes_with_base_terms[record_dict['food_code']] = record_dict['food_base_term']
                food_base_terms = (
                    ('food_base_term', tuple(recipes_with_base_terms[key] for key in recipes_with_base_terms)),
                )
                records_with_no_tags = self._no_tags([
                    self.couch_db.record_to_dict(record) for record in
                    self.couch_db.get_data_from_table(table_name='food_list', fields_and_values=food_base_terms)
                ])
                _fields_and_values = (
                    ('food_code', tuple(el['food_code'] for el in records_with_no_tags)),
                )
                _append(_fields_and_values)

            def _append_for_gap_code_three():
                recipes_with_reference_food_codes = {}
                for record in self.couch_db.get_data_from_table(
                    table_name='food_composition_table', fields_and_values=fields_and_values
                ):
                    record_dict = self.couch_db.record_to_dict(record)
                    if not recipes_with_reference_food_codes.get(record_dict['food_code']):
                        recipes_with_reference_food_codes[record_dict['food_code']] =  \
                            record_dict['reference_food_code_for_food_composition']
                _fields_and_values = (('food_code', tuple(
                    recipes_with_reference_food_codes[code] for code in recipes_with_reference_food_codes)
                ),)
                _append(_fields_and_values)

            def _append_for_gap_code_eight():
                for record in non_std_recipes:
                    if record['data']['fct_gap_code'] == '8':
                        self._set_gap_code_and_description(
                            record['data'], '7', 'ingredient(s) contain fct data gaps'
                        )

            _append_for_gap_code_two()
            _append_for_gap_code_three()
            _append_for_gap_code_eight()

        def _append_gap_code_eight():
            for record in food_items + non_food_items + non_std_recipes:
                self._set_gap_code_and_description(record['data'], '8', 'no fct data available')

        self._append_gap_code_one(food_items, std_recipes)
        self._append_gap_code_two(food_items)
        _append_gap_code_three()
        _append_gap_code_eight()
        _append_gap_code_seven()

    def append_conv_factor_gap_information(self, data):
        food_items, std_recipes, other = self._rearrange_data_for_gap_calculations(data, conv_factor=True)

        def _append_gap_code_eight():
            for record in food_items + std_recipes + other:
                self._set_gap_code_and_description(
                    record['data'], '8', 'no conversion factor available', conv_factor=True
                )

        self._append_gap_code_one(food_items, std_recipes, conv_factor=True)
        self._append_gap_code_two(food_items, conv_factor=True)
        _append_gap_code_eight()

    @staticmethod
    def append_age_information(data):

        def _get_age_range():
            if 0 <= months < 6:
                return '0-5.9 months'
            elif 6 <= months < 60:
                return '06-59 months'
            elif 60 <= months < 84:
                return '5-6 years'
            elif 84 <= months < 132:
                return '7-10 years'
            elif 132 <= months < 180:
                return '11-14 years'
            elif 180 <= months < 600:
                return '15-49 years'
            elif 600 <= months < 780:
                return '50-64 years'
            else:
                return '65+ years'

        for record in data:
            age = record['data']['age']
            if age:
                age = abs(int(age))
                months = age * 12
                record['data']['age_years'] = age
                record['data']['age_months'] = months
                record['data']['age_range'] = _get_age_range()

    @staticmethod
    def _rearrange_data_for_gap_calculations(data, conv_factor=False):
        food_items, std_recipes, non_std_food_item, non_std_recipes = [], [], [], []
        for element in data:
            food_type = element['data']['food_type']
            if food_type == 'food_item':
                food_items.append(element)
            elif food_type == 'std_recipe':
                std_recipes.append(element)
            elif food_type == 'non_std_food_item':
                non_std_food_item.append(element)
            else:
                non_std_recipes.append(element)

        if not conv_factor:
            return food_items, std_recipes, non_std_food_item, non_std_recipes

        return food_items, std_recipes, non_std_food_item + non_std_recipes

    @staticmethod
    def _evaluate_fields_and_values(iterable, number_of_fields, fields_names):
        length = range(number_of_fields)
        result = [set() for i in length]
        for element in iterable:
            records_data = element['data']
            for name in fields_names:
                if records_data.get(name):
                    result[fields_names.index(name)].add(records_data[name])

        return tuple((fields_names[i], tuple(result[i])) for i in length)

    def _get_filtered_data(self, table_name, fields_and_values):
        conv_factor = self.couch_db.get_data_from_table_as_dict(
            table_name=table_name, key_field='food_code',
            fields_and_values=fields_and_values
        )

        return conv_factor, list(conv_factor.keys())

    @staticmethod
    def _set_gap_code_and_description(dict_, new_code, new_desc, conv_factor=False):
        if conv_factor:
            dict_['conv_factor_gap_code'] = new_code
            dict_['conv_factor_gap_desc'] = new_desc
        else:
            dict_['fct_gap_code'] = new_code
            dict_['fct_gap_desc'] = new_desc

    @staticmethod
    def _no_tags(records):
        for record in records.copy():
            for key in record:
                if 'tag' in key and record[key] and 'DONT' not in record[key]:
                    break
            else:
                records.pop(records.index(record))

        return records

    def _append_gap_code_one(self, food_items, std_recipes, conv_factor=False):
        if conv_factor:
            fields_and_values = self._evaluate_fields_and_values(
                food_items + std_recipes, 3, ['food_code', 'conv_method', 'conv_option']
            )
            conv_data, conv_codes = self._get_filtered_data('conv_factors', fields_and_values)
            description = 'conversion factor available'
        else:
            fields_and_values = (
                ('food_code', tuple(record['data']['food_code'] for record in food_items + std_recipes)),
            )
            conv_data, conv_codes = self._get_filtered_data('food_composition_table', fields_and_values)
            description = 'fct data available'

        for record in food_items.copy() + std_recipes.copy():
            if self._record_validation_for_gap_codes_one_and_two(
                record, conv_codes, conv_data, conv_factor=conv_factor
            ):
                if record in food_items:
                    food_items.pop(food_items.index(record))
                else:
                    std_recipes.pop(std_recipes.index(record))
                self._set_gap_code_and_description(
                    record['data'], '1', description, conv_factor=conv_factor
                )
                if conv_factor:
                    self._set_conv_factor_food_information(
                        record['data'], 'food_code', conv_data[record['data']['food_code']]['conv_factor']
                    )
                else:
                    self._set_fct_food_information(record['data'], 'food_code')

    def _append_gap_code_two(self, food_items, conv_factor=False):
        food_base_terms = self._evaluate_fields_and_values(food_items, 1, ['food_base_term'])
        records_with_no_tags = self._no_tags([
            self.couch_db.record_to_dict(record) for record in
            self.couch_db.get_data_from_table(table_name='food_list', fields_and_values=food_base_terms)
        ])
        base_term_food_codes = tuple(element['food_code'] for element in records_with_no_tags)
        if conv_factor:
            fields_and_values = self._evaluate_fields_and_values(
                food_items, 2, ['conv_method', 'conv_option']
            ) + (('food_code', base_term_food_codes),)
            conv_data, conv_codes = self._get_filtered_data('conv_factors', fields_and_values)
            description = 'using conversion factor from base term food code'
        else:
            fields_and_values = (('food_code', base_term_food_codes),)
            conv_data, conv_codes = self._get_filtered_data('food_composition_table', fields_and_values)
            description = 'using fct data from base term food code'

        for record in food_items.copy():
            if self._record_validation_for_gap_codes_one_and_two(
                record, conv_codes, conv_data, conv_factor=conv_factor
            ):
                food_items.pop(food_items.index(record))
                self._set_gap_code_and_description(
                    record['data'], '2', description, conv_factor=conv_factor
                )
                if conv_factor:
                    self._set_conv_factor_food_information(
                        record['data'], 'base_term_food_code',
                        conv_data[record['data']['food_code']]['conv_factor']
                    )
                else:
                    self._set_fct_food_information(record['data'], 'base_term_food_code')

    @staticmethod
    def _record_validation_for_gap_codes_one_and_two(record, conv_codes, conv_data, conv_factor=False):
        if conv_factor:
            return record['data']['food_code'] in conv_codes \
                   and conv_data[record['data']['food_code']]['conv_factor']

        return record['data']['food_code'] in conv_codes

    @staticmethod
    def _set_conv_factor_food_information(data, key_fragment, conv_factor):
        if data['food_type'] in ['food_item', 'std_recipe']:
            data[f'conv_factor_{key_fragment}'] = conv_factor
            data['conv_factor_used'] = key_fragment

    @staticmethod
    def _set_fct_food_information(data, key_fragment):
        if data['food_type'] == 'food_item':
            data[f'fct_{key_fragment}_exists'] = 'yes'
            data['fct_data_used'] = key_fragment
        elif data['food_type'] == 'std_recipe':
            data[f'fct_{key_fragment}_exists'] = 'yes'


class AdditionalFiltersMixin:
    additional_filters = {}

    def filter_fao_who_gift_food_group_description(self, data):
        if self.additional_filters['fao_who_gift_food_group_description']:
            for record in data.copy():
                if record['data']['fao_who_gift_food_group_description'] != \
                        self.additional_filters['fao_who_gift_food_group_description']:
                    data.pop(data.index(record))

    def filter_age_range(self, data):
        if self.additional_filters['age_range']:
            for record in data.copy():
                if record['data']['age_range'] != self.additional_filters['age_range']:
                    data.pop(data.index(record))


class GapsReportDataMixin(ReportDataMixin, AdditionalDataMixin, AdditionalFiltersMixin):

    @property
    def couch_db(self):
        return CouchDbDataCollector(
            domain='inddex-reports', tables=['conv_factors', 'food_list', 'food_composition_table', 'recipes']
        )

    @property
    def additional_filters(self):
        return {
            'gap_type': self.config['gap_type'],
        }

    @property
    def rows(self):
        rows = super().rows
        if self.additional_filters['gap_type'] == 'fct':
            self.append_fct_gap_information(rows)
        elif self.additional_filters['gap_type'] == 'conversion factor':
            self.append_conv_factor_gap_information(rows)
        else:
            self.append_fct_gap_information(rows)
            self.append_conv_factor_gap_information(rows)
        self.append_fao_who_information(rows)
        self._append_nsr_information(rows)

        return rows

    @staticmethod
    def _append_nsr_information(data):
        for record in data:
            el_data = record['data']
            if el_data['nsr_same_conv_method'] == 'yes' and el_data['food_type'] == 'non_std_recipe':
                el_data['nsr_consumed_cooked_fraction'] = \
                    (el_data['conv_size'] * el_data['quantity']) / el_data['nsr_conv_size_post_cooking']


class GapsByItemReportDataMixin(GapsReportDataMixin, AdditionalDataMixin, AdditionalFiltersMixin):

    @property
    def filters(self):
        filters = super().filters
        if self.config['food_type']:
            filters.append(EQ('food_type', 'food_type'))

        return filters

    @property
    def additional_filters(self):
        additional_filters = super().additional_filters
        additional_filters.update(
            fao_who_gift_food_group_description=self.config['fao_who_gift_food_group_description'],
            gap_description=self.config['gap_description']
        )

        return additional_filters

    @property
    def rows(self):
        rows = super().rows
        self.filter_fao_who_gift_food_group_description(rows)
        self._filter_gap_description(rows)

        return rows

    def _filter_gap_description(self, data):
        gap_description = '' if not self.additional_filters['gap_description'] \
            else self.additional_filters['gap_description'].split('-')[1].strip()
        if gap_description:
            for record in data.copy():
                if record['data']['gap_description'] != gap_description:
                    data.pop(data.index(record))


class BaseNutrientDataMixin(ReportDataMixin, AdditionalDataMixin, AdditionalFiltersMixin):

    @property
    def filters(self):
        filters = super().filters
        slugs = ['gender', 'pregnant', 'breastfeeding', 'urban_rural', 'supplements']
        filters += get_slugs(slugs, self.config)

        return filters

    @property
    def rows(self):
        rows = super().rows
        self.append_age_information(rows)
        self.filter_age_range(rows)

        return rows


class NutrientIntakesDataMixin(BaseNutrientDataMixin):

    @property
    def additional_filters(self):
        return {
            'age_range': self.config['age_range']
        }

    @property
    def rows(self):
        rows = super().rows
        self.append_fct_gap_information(rows)
        self.append_conv_factor_gap_information(rows)
        self.append_fao_who_information(rows)
        self.filter_fao_who_gift_food_group_description(rows)

        return rows
