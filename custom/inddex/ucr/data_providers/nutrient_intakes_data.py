from random import randint

from memoized import memoized

from custom.inddex.ucr.data_providers.mixins import NutrientIntakesDataMixin


class NutrientIntakesByFoodData(NutrientIntakesDataMixin):
    title = 'Nutrient Intakes By Food'
    slug = 'nutrient_intake_by_food_data'
    headers_in_order = [
        'food_name', 'recipe_name', 'fao_who_gift_food_group_code', 'fao_who_gift_food_group_description',
        'user_food_group', 'food_type', 'include_in_analysis', 'is_ingredient', 'food_status', 'total_grams',
        'energy_kcal', 'water_g', 'protein_g', '<all other nutrients>', 'conv_factor_gap_code',
        'conv_factor_gap_desc', 'fct_gap_code', 'fct_gap_desc'
    ]

    def __init__(self, config):
        self.config = config

    @property
    @memoized
    def rows(self):
        conv_gaps = {
            1: (1, 'conv factor available'),
            2: (2, 'using conversion factor from base term food code'),
            3: (8, 'no conversion factor available'),
            4: (9, 'not applicable'),
        }
        fac_gaps = {
            1: (1, 'fct data available'),
            2: (2, 'using fct data from base term food code'),
            3: (3, 'using fct data from reference food code'),
            4: (4, 'ingredient(s) contain fct data gaps'),
            5: (8, 'no fct data available'),
            6: (9, 'not applicable'),
        }

        rows = [
            ['Mắm,Nước mắm cá', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '5', '1.7445', '2.56',
             '0.925',
             ''],
            ['Nước luộc,rau', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '299', '0', '15.548',
             '48.139',
             ''],
            ['Cơm,tẻ,nấu', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '147.7136', '', '', '', ''],
            ['Ruốc,cá', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '61.178', '190.691826', '41.478684',
             '31.629026', ''],
            ['Nước luộc,Khác', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '206.74', '0', '10.75048',
             '33.28514', ''],
            ['Bánh mỳ,que,không ngọt', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '250', '', '', '',
             ''],
            ['Đu đủ chín', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '', '', '', '', ''],
            ['Mực khô,nướng', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '59.9155', '174.2941895',
             '27.201637', '46.9138365', ''],
            ['Dưa,cải bẹ', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '574.56', '140.19264',
             '414.25776',
             '51.13584', ''],
            ['Ổi', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '34.2', '', '', '', ''],
            ['Khoai sọ,nấu canh', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '123', '149.2359',
             '83.148',
             '41.574', ''],
            ['Bánh quy,Khác', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '10', '37.81', '6.58', '1.74',
             ''],
            ['Bánh mỳ,Khác,không ngọt', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '48', '', '', '',
             ''],
            ['Bưởi', '', '', '', '', 'food_item', 'yes', '', 'fourth_pass', '', '', '', '', ''],
            ['Canh khoai sọ', 'Canh khoai sọ', '', '', '', 'std_recipe', 'no', '', 'fourth_pass', '200',
             '73.97842',
             '84.71156', '102.6692', ''],
            ['Khoai sọ,sống', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '61.38', '72.98082',
             '22.83336',
             '7.3656', ''],
            ['Rau mùi tàu,sống', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '0.6', '0.1656',
             '0.0294',
             '0.3858', ''],
            ['Hành,lá (hành hoa),sống', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '3.2', '0.832',
             '0.4448', '2.1824', ''],
            ['Gia vị mặn,Bột canh', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '0.6', '0', '0.195',
             '0.2418', ''],
            ['Nước', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '136.02', '0', '61.209', '92.4936',
             ''],
            ['Trứng gà ta ốp la', 'Trứng gà ta ốp la', '', '', '', 'std_recipe', 'no', '', 'fourth_pass', '68', '',
             '',
             '', ''],
            ['Dầu,Hỗn hợp', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '13.022', '117.198',
             '2.851818',
             '6.12034', ''],
            ['Egg,local hen,raw', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '70.8968', '', '', '',
             ''],
            ['ĐẬU PHỤ RÁN XÀO SẢ ỚT', 'ĐẬU PHỤ RÁN XÀO SẢ ỚT', '', '', '', 'non_std_recipe', 'no', '',
             'fourth_pass',
             '5.939406', '4.29617034', '3.756404322', '1.098970092', ''],
            ['(i) Gia vị,Ớt (tươi)', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '0.359964', '0',
             '0.246935304', '0.273212676', ''],
            ['(i) Gia vị,Sả', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '5.579442', '4.29617034',
             '3.509469018', '0.825757416', ''],
            ['QUẢ SUNG MUỐI', 'QUẢ SUNG MUỐI', '', '', '', 'non_std_recipe', 'no', '', 'fourth_pass', '', '', '',
             '',
             ''],
            ['(I) QUẢ SUNY,CẢ VỎ', '', '', '', '', 'non_std_food_item', 'yes', 'yes', 'fourth_pass', '', '', '',
             '',
             ''],
            ['(i) Mắm,Nước mắm cá', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '7.5636363636',
             '2.6389527273', '3.8725818182', '1.3992727273', ''],
            ['(i) Giấm (gạo/bỗng/táo….)', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '2.9381818182',
             '0',
             '1.0577454545', '0.4994909091', ''],
            ['(i) Đường,kính', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '9.8909090909',
             '39.2866909091', '2.5815272727', '1.7605818182', ''],
            ['(i) Bột,Khác', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '2.9090909091',
             '10.4843636364',
             '1.4225454545', '0.4829090909', ''],
            ['NƯỚC NGHỆ MẬT ONG', 'NƯỚC NGHỆ MẬT ONG', '', '', '', 'non_std_recipe', 'no', '', 'fourth_pass', '',
             '',
             '', '', ''],
            ['(I) BỘT NGHỆ,BỘT NGHỆ XAY', '', '', '', '', 'non_std_food_item', 'yes', 'yes', 'fourth_pass', '', '',
             '',
             '', ''],
            ['(i) Mật ong', '', '', '', '', 'food_item', 'yes', 'yes', 'fourth_pass', '', '', '', '', ''],
            ['NƯỚC ĐẬU,NƯỚC ĐẬU TƯƠI THÊM ĐƯỜNG VÀ ĐÁ', '', '', '', '', 'non_std_food_item', 'yes', '',
             'fourth_pass',
             '', '', '', '', ''],
        ]

        for row in rows:
            food_type = row[5]
            if food_type not in ['food_item', 'std_food_item ']:
                x, y = 4, 6
            else:
                x = randint(1, 3)
                y = randint(1, 5)
            conv = conv_gaps[x]
            fac = fac_gaps[y]
            row.extend([conv[0], conv[1], fac[0], fac[1]])

        return rows


class NutrientIntakesByRespondentData(NutrientIntakesDataMixin):
    title = 'Nutrient Intakes By Respondent'
    slug = 'nutrient_intakes_by_respondent'
    headers_in_order = [
        'unique_respondent_id', 'recall_case_id', 'opened_by_username', 'owner_name',
        'recall_date', 'recall_status', 'gender', 'age_years', 'age_months', 'age_range', 'supplements',
        'urban_rural', 'pregnant', 'breastfeeding', 'energy_kcal', 'water_g', 'protein_g', '<all other nutrients>'
    ]

    def __init__(self, config):
        super().__init__(config)

    @property
    @memoized
    def rows(self):
        return [
            ['555_1', 'f3bfc88d-6cb1-4ae8-acdc-9715a9411b13', 'mary', 'mary', '2019-08-12', 'Complete', 'female',
             '23',
             '276', '15-49 years', 'no', 'urban', 'no', 'no', '140.19264', '140.19264', '140.19264', ''],
            ['555_2', 'f3bfc88d-6cb1-4ae8-acdc-9715a9411b14', 'mary', 'mary', '2019-08-12', 'Complete', 'female',
             '23',
             '276', '15-49 years', 'no', 'urban', 'no', 'no', '140.19264', '140.19264', '140.19264', ''],
            ['666_1', '36271593-cb0d-4a99-ac35-260db7d4b63e', 'sue', 'sue', '2019-08-14', 'Complete', 'female',
             '29',
             '348', '15-49 years', 'yes', 'peri-urban', 'no', 'no', '0', '26.29848', '81.42414', ''],
            ['888_1', 'de16bd5b-51bc-4dac-ba81-50e04ac858e5', 'mary', 'mary', '2019-08-14', 'Complete', 'female',
             '29',
             '348', '15-49 years', 'yes', 'rural', 'yes', 'no', '0', '0', '0', ''],
            ['8003_1', '832b98ad-303f-458d-a400-1f8453b358c6', 'mary', 'mary', '2019-08-14', 'Complete', 'male',
             '52',
             '624', '50-64 years', 'no', 'urban', 'no', 'no', '0', '0', '0', ''],
            ['12345_1', 'fbcc5cd9-3d8c-43c8-908d-abb1c0b21089', 'sue', 'sue', '2019-08-17', 'Complete', 'male',
             '23',
             '276', '15-49 years', 'no', 'urban', 'yes', 'no', '140.19264', '414.25776', '51.13584', ''],
            ['8007_1', '225281cf-ae7e-4d20-9516-0e64c228467e', 'sue', 'sue', '2019-08-17', 'Complete', 'female',
             '1',
             '14', '6-59 months', 'yes', 'rural', 'no', 'yes', '239.4559072727', '98.6624', '47.4562545455', ''],
            ['444567_1', 'e22a2245-8370-45b5-aea7-f2b8728dbc5e', 'john', 'john', '2019-08-17', 'Complete', 'male',
             '22',
             '264', '15-49 years', 'no', 'urban', 'no', 'no', '0', '0', '0', ''],
            ['1234_1', '738d5457-3517-4ef0-b21e-65a7ded2e8d1', 'sue', 'sue', '2019-08-17', 'Complete', 'male',
             '23',
             '276', '15-49 years', 'no', 'urban', 'no', 'no', '4.29617034', '3.756404322', '1.098970092', ''],
        ]
