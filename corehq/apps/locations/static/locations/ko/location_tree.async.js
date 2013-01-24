
function api_get_children(loc_uuid, callback) {
    var params = (loc_uuid ? {parent_id: loc_uuid} : {});
    $.getJSON(LOAD_LOCS_URL, params, function(allData) {
            callback(allData.objects);
        });
}

function LocationTreeViewModel() {
    var model = this;
    
    this.root = ko.observable();
    
    // search for a location within the tree by uuid; return path to location if found
    this.find_loc = function(uuid, loc) {
        loc = loc || this.root();
        
        if (loc.uuid() == uuid) {
            return [loc];
        } else {
            var path = null;
            $.each(loc.children(), function(i, e) {
                    var subpath = model.find_loc(uuid, e);
                    if (subpath) {
                        path = subpath;
                        path.splice(0, 0, loc);
                        return false;
                    }
                });
            return path;
        }
    }
    
    // load location hierarchy
    this.load = function(locs) {
        this.root(new LocationModel({name: '_root', children: locs}, this));
        this.root().expanded(true);
    }
}

function LocationModel(data, root, depth) {
    var loc = this;
    
    this.name = ko.observable();
    this.type = ko.observable();
    this.uuid = ko.observable();
    this.children = ko.observableArray();
    this.depth = depth || 0;
    this.can_have_children = ko.observable(true);
    this.children_status = ko.observable('not_loaded');
    this.expanded = ko.observable(false);
    
    this.expanded.subscribe(function(val) {
            if (val && this.children_status() == 'not_loaded') {
                this.load_children_async();
            }
        }, this);
    
    this.toggle = function() {
        this.expanded(!this.expanded());
    }

    this.load = function(data) {
        this.name(data.name);
        this.type(data.location_type);
        this.uuid(data.uuid);
        if (data.children != null) {
            this.set_children(data.children);
        }

        // TODO this should reference location type settings for domain
        if (this.type() == 'outlet') {
            this.can_have_children(false);
        }
    }
    
    this.set_children = function(data) {
        var children = [];
        if (data) {
            children = _.sortBy(data, function(e) { return e.name; });
        }
        this.children($.map(children, function(e) {
                    return new LocationModel(e, root, loc.depth + 1);
                }));
        this.children_status('loaded');
    }
    
    this.load_children_async = function(callback) {
        this.children_status('loading');
        api_get_children(this.uuid(), function(resp) {
                loc.set_children(resp);
                if (callback) {
                    callback(loc);
                }
            });
    }
    
    this.load(data);
}
