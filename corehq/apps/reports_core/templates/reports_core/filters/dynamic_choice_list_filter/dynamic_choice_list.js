{% load reports_core_tags %}
{% load hq_shared_tags %}
// note: this depends on choice-list-api.js
var filter_id = "#{{ context_.css_id }}-input",
    initialValues = _.map({{context_.value|JSON}}, function(value){
        return choiceListUtils.formatValueForSelect2(value);
    }),
// TODO: Ideally the separator would be defined in one place. Right now it is
//       also defined corehq.apps.userreports.reports.filters.CHOICE_DELIMITER
    separator = "\u001F";

$(filter_id).select2({
    minimumInputLength: 0,
    multiple: true,
    separator: separator,
    allowClear: true,
    // allowClear only respected if there is a non empty placeholder
    placeholder: " ",
    ajax: {
        url: "{% ajax_filter_url domain report filter %}",
        dataType: 'json',
        quietMillis: 250,
        data: choiceListUtils.getApiQueryParams,
        results: choiceListUtils.formatPageForSelect2,
        cache: true
    }
});
$(filter_id).select2('data', initialValues);
