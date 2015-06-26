{% load reports_core_tags %}
var filter_id = "#{{ filter.css_id }}-input";
var pageSize = 20;
$(filter_id).select2({
    minimumInputLength: 0,
    allowClear: true,
    // allowClear only respected if there is a non empty placeholder
    placeholder: " ",
    ajax: {
        url: "{% ajax_filter_url domain report filter %}",
        dataType: 'json',
        quietMillis: 250,
        data: function (term, page) {
            return {
                q: term, // search term
                page: page,
                limit: pageSize
            };
        },
        results: function (data, page) {
            // parse the results into the format expected by Select2.
            var formattedData = _.map(data, function (val) { return {'id': val, 'text': val}});
            return {
                results: formattedData,
                more: data.length === pageSize
            };
        },
        cache: true
    }
});
$('#{{ filter.css_id }}').find('.select2-chosen')[0].innerHTML = $(filter_id).val();
