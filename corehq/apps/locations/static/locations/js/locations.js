import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import locationModels from "locations/js/location_tree";

$(function () {
    const locs = initialPageData.get('locations'),
        canEditRoot = initialPageData.get('can_edit_root'),
        hierarchy = initialPageData.get('hierarchy'),
        showInactive = initialPageData.get('show_inactive');

    var options = {
        show_inactive: showInactive,
        can_edit_root: canEditRoot,
    };

    var treeModel = locationModels.locationTreeViewModel(hierarchy, options);

    $('#location_tree').koApplyBindings(treeModel);
    treeModel.load(locs);

    var model = locationModels.locationSearchViewModel(treeModel, options);
    $('#location_search').koApplyBindings(model);
});
