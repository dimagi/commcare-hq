function IntrahealthLocModel(data, root, depth) {
    var loc = this;
    LocationModel.apply(this, [data, root, depth, IntrahealthLocModel, false]);

    this.load_children_async = function(callback) {
        if (this.depth < root.location_types.length) {
            api_get_children(this.uuid(), function (resp) {
                loc.set_children(resp);
                callback(loc);
            });
        }
    };
}