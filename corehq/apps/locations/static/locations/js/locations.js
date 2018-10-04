hqDefine('locations/js/locations', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'locations/js/utils',
    'locations/js/location_tree',
], function (
    $,
    initialPageData,
    locationUtils,
    locationModels
) {
    $(function () {
        var locs = initialPageData.get('locations'),
            can_edit_root = initialPageData.get('can_edit_root'),
            hierarchy = initialPageData.get('hierarchy'),
            show_inactive = initialPageData.get('show_inactive');

        var options = {
            show_inactive: show_inactive,
            can_edit_root: can_edit_root,
        };

        var tree_model = locationModels.locationTreeViewModel(hierarchy, options);

        $('#location_tree').koApplyBindings(tree_model);
        tree_model.load(locs);

        var model = locationModels.locationSearchViewModel(tree_model, options);
        $('#location_search').koApplyBindings(model);

        locationUtils.enableLocationSearchSelect();
    });
});
