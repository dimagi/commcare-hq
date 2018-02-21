hqDefine("domain/js/info_base", function() {
    $(function() {
        _.each(hqImport('hqwebapp/js/initial_page_data').get('autocomplete_fields'), function(field) {
            $("#id_" + field).focus(function() {
                if (!$("#id_" + field).data('loaded')) {
                    $("#id_" + field).data('loaded', 'true');
                    $.getJSON(hqImport("hqwebapp/js/initial_page_data").reverse("domain_autocomplete_fields", field), function(results) {
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
