// for product and user per location selection
hqDefine("locations/js/location", [
    'jquery',
    'knockout',
    'underscore',
    'es6!hqwebapp/js/bootstrap5_loader',
    'hqwebapp/js/initial_page_data',
    'analytix/js/google',
    'locations/js/location_drilldown',
    'locations/js/location_tree',
    'hqwebapp/js/select_2_ajax_widget',
    'hqwebapp/js/bootstrap5/widgets',       // custom data fields use a .hqwebapp-select2
    'locations/js/widgets',
    'commcarehq',
], function (
    $,
    ko,
    _,
    bootstrap,
    initialPageData,
    googleAnalytics,
    locationModels,
    locationTreeModel
) {
    $(function () {

        var locationUrl = initialPageData.get('api_root');
        var locId = initialPageData.get('location_id');
        var locType = initialPageData.get('location_type');
        var hierarchy = initialPageData.get('hierarchy');

        var model = locationModels.locationSelectViewModel({
            "hierarchy": hierarchy,
            "default_caption": "\u2026",
            "auto_drill": false,
            "loc_filter": function (loc) {
                return loc.uuid() !== locId && loc.can_have_children();
            },
            "loc_url": locationUrl,
        });
        model.editing = ko.observable(false);
        model.allowed_child_types = ko.computed(function () {
            var activeLoc = (this.selected_location() || this.root());
            return (activeLoc ? activeLoc.allowed_child_types() : []);
        }, model);
        model.loc_type = ko.observable(locType);

        var locs = initialPageData.get('locations');
        var selectedParent = initialPageData.get('location_parent_get_id');
        model.load(locs, selectedParent);
        model.orig_parent_id = model.selected_locid();

        $("#loc_form :button[type='submit']").click(function () {
            if (this.name === 'update-loc') {
                googleAnalytics.track.event('Organization Structure', 'Edit', 'Update Location');
            } else {
                googleAnalytics.track.event('Organization Structure', 'Edit', 'Create Child Location');
            }
        });

        googleAnalytics.track.click($("#edit_users :button[type='submit']"), 'Organization Structure', 'Edit', 'Update Users at this Location');

        $('#loc_form').koApplyBindings(model);

        var options = {
            show_inactive: initialPageData.get('show_inactive'),
            can_edit_root: true,
        };

        var location = initialPageData.get('location');
        if (location) {
            var locData = {
                name: location.name,
                location_type: location.location_type,
                uuid: locId,
                is_archived: location.is_archived,
                can_edit: options.can_edit_root,
            };

            var treeModel = locationTreeModel.locationTreeViewModel(hierarchy, options);
            treeModel.load(locs);

            var pseudoRootLocation = locationTreeModel.locationModel(locData, treeModel, 1);
            treeModel.root = pseudoRootLocation;

            $('#location_tree').koApplyBindings(treeModel);
        }
    });
});
