hqDefine("domain/js/info_base", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'bootstrap3-typeahead/bootstrap3-typeahead.min',
    'hqwebapp/js/bootstrap-multi-typeahead',
], function(
    $,
    _,
    initialPageData
) {
    $(function() {
        _.each(initialPageData.get('autocomplete_fields'), function(field) {
            $("#id_" + field).focus(function() {
                if (!$("#id_" + field).data('loaded')) {
                    $("#id_" + field).data('loaded', 'true');
                    $.getJSON(initialPageData.reverse("domain_autocomplete_fields", field), function(results) {
                        $("#id_" + field).typeahead({
                            source: results,
                            items: 8,
                        }).attr("autocomplete", "off");
                    });
                }
            });
        });
    });
});
