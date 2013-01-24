
function api_get_children(loc_uuid, callback) {
    var params = (loc_uuid ? {parent_id: loc_uuid} : {});
    $.getJSON(LOAD_LOCS_URL, params, function(allData) {
            callback(allData.objects);
        });
}

function LocationTreeViewModel() {
    var model = this;
    
    this.root = ko.observable();
    
    // TODO this should reference location type settings for domain
    this.location_types = [
        {type: 'state', allowed_parents: [null]},
        {type: 'district', allowed_parents: ['state']},
        {type: 'block', allowed_parents: ['district']},
        {type: 'village', allowed_parents: ['block']},
        {type: 'outlet', allowed_parents: ['village', 'block']},
    ];

    // search for a location within the tree by uuid; return path to location if found (not used atm)
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
    this.children_status = ko.observable('not_loaded');
    this.expanded = ko.observable(false);
    
    this.expanded.subscribe(function(val) {
            if (val && this.children_status() == 'not_loaded') {
                this.load_children_async();
            }
        }, this);
    
    this.toggle = function() {
        this.expanded(!this.expanded() && this.can_have_children());
    }

    this.load = function(data) {
        this.name(data.name);
        this.type(data.location_type);
        this.uuid(data.uuid);
        if (data.children != null) {
            this.set_children(data.children);
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
   
    this.allowed_child_types = function() {
        var loc = this;
        var types = [];
        $.each(root.location_types, function(i, loc_type) {
                $.each(loc_type.allowed_parents, function(i, parent_type) {
                        if (loc.type() == parent_type) {
                            types.push(loc_type.type);
                        }
                    });
            });
        return types;
    };

    this.can_have_children = ko.computed(function() {
            return (this.allowed_child_types().length > 0);
        }, this);

    this.allowed_child_type = function() {
        var types = this.allowed_child_types();
        return (types.length == 1 ? types[0] : null);
    }

    this.new_child_caption = ko.computed(function() {
            var child_type = this.allowed_child_type();
            var top_level = (this.name() == '_root');
            return 'New ' + (child_type || 'location') + (top_level ? ' at top level' : ' in ' + this.name() + ' ' + this.type());
        }, this);
 
    this.no_children_caption = ko.computed(function() {
            var child_type = this.allowed_child_type();
            var top_level = (this.name() == '_root');

            // TODO replace 'location' with proper type as applicable (what about pluralization?)
            return (top_level ? 'No locations created in this project yet' : 'No sub-locations inside ' + this.name());
        }, this);

    this.load(data);
}
