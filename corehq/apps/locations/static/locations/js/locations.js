hqDefine('locations/js/locations', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');

    function loc_edit_url(loc_id) {
        var template = initialPageData.reverse('edit_location');
        return template.replace('-locid-', loc_id);
    }

    var enableLocationSearchSelect = function() {
        $('#location_search_select').select2({
            ajax: {
                url: initialPageData.reverse('location_search'),
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

    $(function() {
        var LOAD_LOCS_URL = initialPageData.get('api_root'),
            NEW_LOC_URL = initialPageData.reverse("create_location");

        var locs = initialPageData.get('locations');
        var can_edit_root = initialPageData.get('can_edit_root');
        var hierarchy = initialPageData.get('hierarchy');
        var show_inactive = initialPageData.get('show_inactive');

        $('#location_tree').koApplyBindings(tree_model);
        tree_model.load(locs);
        var model = new LocationSearchViewModel(tree_model);
        $('#location_search').koApplyBindings(model);
    });
});
