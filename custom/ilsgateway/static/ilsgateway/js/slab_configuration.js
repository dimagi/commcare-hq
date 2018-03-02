hqDefine('ilsgateway/js/locations', function () {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    var LocationModels = hqImport('locations/js/location_tree');

    $(function () {
        var load_locs_url = initialPageData.get('api_root'),
            new_loc_url = initialPageData.reverse("create_location");

        var locs = initialPageData.get('locations'),
            can_edit_root = initialPageData.get('can_edit_root'),
            hierarchy = initialPageData.get('hierarchy'),
            show_inactive = initialPageData.get('show_inactive'),
            edit_location_url = initialPageData.reverse('slab_edit_location');

        function loc_edit_url(loc_id) {
            var template = edit_location_url;
            return template.replace('-locid-', loc_id);
        }

        var options = {
            show_inactive: show_inactive,
            can_edit_root: can_edit_root,
            load_locs_url: load_locs_url,
            new_loc_url: new_loc_url,
            loc_edit_url: loc_edit_url,
        };

        var tree_model = new LocationModels.LocationTreeViewModel(hierarchy, options);

        $('#location_tree').koApplyBindings(tree_model);
        tree_model.load(locs);
    });
});
