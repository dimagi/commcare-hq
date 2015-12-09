{% load reports_core_tags %}
// note: this depends on choice-list-api.js
var filter_id = "#{{ filter.css_id }}-input";
// TODO: Ideally the separator would be defined in one place. Right now it is
//       also defined corehq.apps.userreports.reports.filters.CHOICE_DELIMITER
var separator = "\u001F";
var initialValues = $(filter_id).val() !== "" ? $(filter_id).val().split(separator) : [];
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
$(filter_id).select2('data', _.map(initialValues, function(v){
    return {id: v, text: v};
}));
