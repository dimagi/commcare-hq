from memoized import memoized

from custom.inddex.ucr.data_providers.mixins import GapsReportDataMixin


class MasterDataFileData(GapsReportDataMixin):
    title = 'Master Data'
    slug = 'master_data'
    headers_in_order = [
        'unique_respondent_id', 'location_id', 'respondent_id', 'recall_case_id', 'opened_date', 
        'opened_by_username', 'owner_name', 'recall_date', 'recall_status', 'gender', 'age_years', 'age_months', 
        'age_range', 'pregnant', 'breastfeeding', 'supplements', 'urban_rural', 'food_code', 'food_name', 
        'recipe_name', 'caseid', 'reference_food_code', 'food_type', 'include_in_analysis', 'food_status', 
        'eating_time', 'time_block', 'fao_who_gift_food_group_code', 'fao_who_gift_food_group_description', 
        'user_food_group', 'already_reported_food', 'already_reported_food_caseid', 'already_reported_recipe',
        'already_reported_recipe_case_id', 'already_reported_recipe_name', 'is_ingredient', 'recipe_case_id', 
        'ingr_recipe_code', 'ingr_fraction', 'ingr_recipe_total_grams_consumed', 'short_name', 'food_base_term', 
        'tag_1', 'other_tag_1', 'tag_2', 'other_tag_2', 'tag_3', 'other_tag_3', 'tag_4',
        'other_tag_4', 'tag_5', 'other_tag_5', 'tag_6', 'other_tag_6', 'tag_7', 'other_tag_7', 'tag_8',
        'other_tag_8', 'tag_9', 'other_tag_9', 'tag_10', 'conv_method', 'conv_method_desc',
        'conv_option', 'conv_option_desc', 'conv_size', 'conv_units', 'quantity',
        'nsr_conv_method_code_post_cooking', 'nsr_conv_method_desc_post_cooking',
        'nsr_conv_option_code_post_cooking', 'nsr_conv_option_desc_post_cooking', 'nsr_conv_size_post_cooking',
        'nsr_consumed_cooked_fraction', 'recipe_num_ingredients', 'conv_factor_food_code',
        'conv_factor_base_term_food_code', 'conv_factor_used', 'fct_food_code_exists',
        'fct_base_term_food_code_exists', 'fct_reference_food_code_exists', 'fct_data_used', 'total_grams',
        'energy_per_100g', 'energy_kcal', 'water_per_100g', 'water_g', 'protein_per_100g', 'protein_g',
        'conv_factor_gap_code', 'conv_factor_gap_desc', 'fct_gap_code', 'fct_gap_desc'
    ]

    def __init__(self, config):
        self.config = config

    @property
    def obligatory_couch_names(self):
        return super().obligatory_couch_names + ['nsr_same_conv_method']

    @property
    @memoized
    def rows(self):
        rows = super().rows
        self.append_age_information(rows)
        self._append_recipe_information(rows)

        return self.rearrange_data(rows)

    def _append_recipe_information(self, data):
        fields_and_values = (
            ('recipe_code', tuple(
                element['data']['food_code']
                for element in data
                if element['data']['food_type'] in ['std_recipe', 'non_std_recipe']
            )),
        )
        recipe_information = {}
        for record in self.couch_db.get_data_from_table(table_name='recipes', fields_and_values=fields_and_values):
            record_dict = self.couch_db.record_to_dict(record)
            recipe_code = record_dict['recipe_code']
            ingr_code = record_dict['ingr_code']
            if not recipe_information.get(recipe_code):
                recipe_information[recipe_code] = {ingr_code}
            else:
                recipe_information[recipe_code].add(ingr_code)

        for record in data:
            el_data = record['data']
            if el_data['food_code'] in recipe_information:
                el_data['recipe_num_ingredients'] = str(len(recipe_information[el_data['food_code']]))
