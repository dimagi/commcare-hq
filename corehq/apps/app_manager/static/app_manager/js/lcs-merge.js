/*
    Adapted from the algorithms presented on
    http://en.wikipedia.org/wiki/Longest_common_subsequence_problem

    lcsMerge returns the "unified diff" of two sequences.
    If you read off [item.token for item in lcsMerge(X, Y) if item.x]
    you should get back X. (And analogously for Y.)
 */
function lcsMerge(X, Y, isEqual) {
    'use strict';
    isEqual = isEqual || function (a, b) {
        return a === b;
    };
    var cache = {};
    cache.get = function (i, j) {
        var cache_key = i + ' ' + j;
        var val = cache[cache_key];
        if (val) {
            return {
                lcs_length: val.lcs_length,
                merge: val.merge.slice(0)
            };
        } else {
            return null;
        }
    };
    cache.set = function (i, j, val) {
        var cache_key = i + ' ' + j;
        cache[cache_key] = val;
    };
    function recLcsMerge(i, j) {
        var val, val1, val2, recur = recLcsMerge;
        val = cache.get(i, j);
        if (val) {
            return val;
        }
        if (i === 0 && j === 0) {
            val = {
                lcs_length: 0,
                merge: []
            };
        } else if (i === 0) {
            val = recur(i, j - 1);
            val.merge.push({x: false, y: true, token: Y[j - 1]});
        } else if (j === 0) {
            val = recur(i - 1, j);
            val.merge.push({x: true, y: false, token: X[i - 1]});
        } else if (isEqual(X[i - 1], Y[j - 1])) {
            val = recur(i - 1, j - 1);
            val.lcs_length++;
            val.merge.push({x: true, y: true, token: X[i - 1]});
        } else {
            val1 = recur(i, j - 1);
            val2 = recur(i - 1, j);
            if (val2.lcs_length > val1.lcs_length) {
                val = val2;
                val.merge.push({x: true, y: false, token: X[i - 1]});
            } else {
                val = val1;
                val.merge.push({x: false, y: true, token: Y[j - 1]});
            }
        }
        cache.set(i, j, val);
        return cache.get(i, j);
    }

    return recLcsMerge(X.length, Y.length).merge;
}


lcsMerge.test = function () {
    var spec = {
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
    };
    var expectedFields = [
        "name", "name", "quarter", "date_last_visit", "phone_number",
        "parent/parent/phone_number", "dob", "nutrition_status"
    ];
    var fields = _.pluck(
        _.pluck(
            lcsMerge(spec.short.columns, spec.long.columns, _.isEqual),
            'token'
        ),
        'field'
    );
    if (!_.isEqual(fields, expectedFields)) {
        throw {
            'expected': expectedFields,
            'actual': fields
        };
    }
};
