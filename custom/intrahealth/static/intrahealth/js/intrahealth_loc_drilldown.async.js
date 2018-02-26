hqDefine('intrahealth/js/location_drilldown', function() {
    var locationDrilldown = hqImport('locations/js/location_drilldown'),
        LocationModel = locationDrilldown.LocationModel,
        api_get_children = locationDrilldown.api_get_children;

    function IntrahealthLocModel(data, root, depth) {
        var loc = this;
        LocationModel.apply(this, [data, root, depth, IntrahealthLocModel, false]);

        this.load_children_async = function(callback) {
            if (this.depth < root.location_types.length) {
                api_get_children(this.uuid(), function (resp) {
                    loc.set_children(resp);
                    callback(loc);
                }, root.loc_url);
            }
        };
    }

    return { IntrahealthLocModel: IntrahealthLocModel };
});
