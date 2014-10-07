class LCSCache(object):
    def __init__(self):
        self.d = {}

    def get(self, i, j):
        key = str(i) + ' ' + str(j)
        try:
            val = self.d[key]
            return {
                "lcs_length": val['lcs_length'],
                "merge": val["merge"][:]
            }
        except KeyError:
            return None

    def set(self, i, j, val):
        key = str(i) + ' ' + str(j)
        self.d[key] = val


def lcsMerge(X, Y, equality_func=None):
    # Duplicated from here:
    # https://github.com/dimagi/commcare-hq/blob/7cec2e62ea84e996ec1bb5fa2dda128be304ae1c/corehq/apps/app_manager/static/app_manager/js/lcs-merge.js
    if equality_func is None:
        equality_func = lambda x, y: x == y
    cache = LCSCache()

    def recLcsMerge(i, j):
        recur = recLcsMerge
        val = cache.get(i, j)
        if val:
            return val
        if i == 0 and j == 0:
            val = {
                'lcs_length': 0,
                'merge': []
            }
        elif i == 0:
            val = recur(i, j - 1)
            val['merge'].append({"x": False, "y": True, "token": Y[j - 1]})
        elif j == 0:
            val = recur(i - 1, j)
            val['merge'].append({'x': True, 'y': False, 'token': X[i - 1]})
        elif equality_func(X[i - 1], Y[j - 1]):
            val = recur(i - 1, j - 1)
            val['lcs_length'] = val['lcs_length'] + 1
            val['merge'].append({'x': True, 'y': True, 'token': X[i - 1]})
        else:
            val1 = recur(i, j - 1)
            val2 = recur(i - 1, j)
            if val2['lcs_length'] > val1['lcs_length']:
                val = val2
                val['merge'].append({"x": True, "y": False, "token": X[i - 1]})
            else:
                val = val1
                val['merge'].append({'x': False, 'y': True, 'token': Y[j - 1]})
        cache.set(i, j, val)
        return cache.get(i, j)
    return recLcsMerge(len(X), len(Y))['merge']


def _test():
    spec = {
        "short": {
            "columns": [
                {"doc_type": "DetailColumn", "filter_xpath": "today() <= date(date(dob) + 1826)", "format": "filter", "late_flag": 30, "enum": [], "header": {"en": "Name", "hat": "Non"}, "time_ago_interval": 365.25, "calc_xpath": ".", "field": "name", "model": "case", "advanced": ""},
                {"doc_type": "DetailColumn", "filter_xpath": "", "format": "plain", "late_flag": 30, "enum": [], "header": {"en": "Name", "hat": "Non"}, "time_ago_interval": 365.25, "field": "name", "calc_xpath": "concat(mother_name, ' - ', .)", "model": "case", "advanced": ""},
                {"doc_type": "DetailColumn", "filter_xpath": "", "format": "plain", "late_flag": 30, "enum": [], "header": {"en": "Quarter", "hat": "Katye"}, "time_ago_interval": 365.25, "field": "quarter", "calc_xpath": ".", "model": "case", "advanced": ""},
                {"doc_type": "DetailColumn", "filter_xpath": "", "format": "time-ago", "late_flag": 30, "enum": [], "header": {"en": "Weeks Since Visit", "hat": "Semen Depi Denye Vizit"}, "time_ago_interval": 7.0, "field": "date_last_visit", "calc_xpath": ".", "model": "case", "advanced": ""}
            ]
        },
        "long": {
            "columns": [
                {"doc_type": "DetailColumn", "filter_xpath": "", "format": "plain", "late_flag": 30, "enum": [], "header": {"en": "Name", "hat": "Non"}, "time_ago_interval": 365.25, "field": "name", "calc_xpath": "concat(mother_name, ' - ', .)", "model": "case", "advanced": ""},
                {"doc_type": "DetailColumn", "filter_xpath": "", "format": "plain", "late_flag": 30, "enum": [], "header": {"en": "Quarter", "hat": "Katye"}, "time_ago_interval": 365.25, "field": "quarter", "calc_xpath": ".", "model": "case", "advanced": ""},
                {"doc_type": "DetailColumn", "filter_xpath": "", "format": "phone", "late_flag": 30, "enum": [], "header": {"en": "Phone Number", "hat": "Nimewo telephon"}, "time_ago_interval": 365.25, "field": "phone_number", "calc_xpath": ".", "model": "case", "advanced": ""},
                {"doc_type": "DetailColumn", "filter_xpath": "", "format": "phone", "late_flag": 30, "enum": [], "header": {"en": "Phone Number", "hat": "Nimewo telephon"}, "time_ago_interval": 365.25, "field": "parent/parent/phone_number", "calc_xpath": ".", "model": "case", "advanced": ""},
                {"doc_type": "DetailColumn", "filter_xpath": "", "format": "time-ago", "late_flag": 30, "enum": [], "header": {"en": "Age (months)", "hat": "Gen Laj Nan Mwa"}, "time_ago_interval": 30.4375, "field": "dob", "calc_xpath": ".", "model": "case", "advanced": ""},
                {"doc_type": "DetailColumn", "filter_xpath": "", "format": "enum", "late_flag": 30, "enum": [{"doc_type": "MappingItem", "key": "sam", "value": {"en": "Severe Malnutrition", "hat": "Malnutrition aigue severe"}},{"doc_type": "MappingItem", "key": "mam", "value": {"en": "Moderate Malnutrition", "hat": "Malnutrition aigue moderee"}},{"doc_type": "MappingItem", "key": "risky", "value": {"en": "At Risk of Malnutrition", "hat": "A risque de malnutrition"}}, {"doc_type": "MappingItem", "key": "normal", "value": {"en": "Normal", "hat": "Normal"}}], "header": {"en": "Nutrition Status", "hat": "Etat Nutritionnel"}, "time_ago_interval": 365.25, "field": "nutrition_status", "calc_xpath": ".", "model": "case", "advanced": ""}
            ]
        }
    }
    expectedFields = [
        "name", "name", "quarter", "date_last_visit", "phone_number",
        "parent/parent/phone_number", "dob", "nutrition_status"
    ]
    fields = [
        x['token']['field'] for x in lcsMerge(
            spec['short']['columns'], spec['long']['columns']
        )
    ]
    if not fields == expectedFields:
        print "bad"
    else:
        print "good"