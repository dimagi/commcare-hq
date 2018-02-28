hqDefine('locations/js/locations', function() {
    var LOAD_LOCS_URL = '{{ api_root }}',
        NEW_LOC_URL = '{% url "create_location" domain %}';

    var locs = {{ locations|JSON }};
    var can_edit_root = {{ can_edit_root|yesno:"true,false" }};
    var hierarchy = {{ hierarchy|JSON }};
    var show_inactive = {{ show_inactive|yesno:"true,false" }};

    function loc_edit_url(loc_id) {
        var template = '{% url "edit_location" domain "-locid-" %}';
        return template.replace('-locid-', loc_id);
    }

    var enableLocationSearchSelect = function() {

        $('#location_search_select').select2({
            ajax: {
                url: '{% url 'location_search' domain %}',
                dataType: 'json',
                data: function (params) {
                    return {
                        q: params.term,
                        page_limit: 10,
                        page: params.page,
                        show_inactive: show_inactive,
                    };
                },
                processResults: function (data, params) {
                    var more = data.more || (params.page * 10) < data.total;
                    return {results: data.results, more: more};
                }
            },
        });
    };

    var tree_model = new LocationTreeViewModel(hierarchy);

    var reloadLocationSearchSelect = function() {
        $('#location_search_select').select2('val', null);
        enableLocationSearchSelect();
    };

    var clearLocationSelection = function() {
        reloadLocationSearchSelect();
        tree_model.load(locs);
    };

    enableLocationSearchSelect();

    $(function() {
        $('#location_tree').koApplyBindings(tree_model);
        tree_model.load(locs);
        var model = new LocationSearchViewModel(tree_model);
        $('#location_search').koApplyBindings(model);
    });
});
