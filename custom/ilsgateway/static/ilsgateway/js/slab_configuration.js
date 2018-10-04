hqDefine('ilsgateway/js/locations', function () {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    var LocationModels = hqImport('locations/js/location_tree');

    $(function () {
        var locs = initialPageData.get('locations'),
            can_edit_root = initialPageData.get('can_edit_root'),
            hierarchy = initialPageData.get('hierarchy'),
            show_inactive = initialPageData.get('show_inactive');

        var options = {
            show_inactive: show_inactive,
            can_edit_root: can_edit_root,
        };

        var treeModel = LocationModels.locationTreeViewModel(hierarchy, options);

        $('#location_tree').koApplyBindings(treeModel);
        treeModel.load(locs);
    });
});
