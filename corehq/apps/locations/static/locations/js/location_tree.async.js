
function api_get_children(loc_uuid, callback) {
    var params = (loc_uuid ? {parent_id: loc_uuid} : {});
    // show_inactive comes from global state
    params.include_inactive = show_inactive;
    $.getJSON(LOAD_LOCS_URL, params, function(allData) {
        callback(allData.objects);
    });
}

function LocationTreeViewModel(hierarchy) {
    var model = this;

    this.root = ko.observable();

    // TODO this should reference location type settings for domain
    this.location_types = $.map(hierarchy, function(e) {
        return {type: e[0], allowed_parents: e[1]};
    });

    // search for a location within the tree by uuid; return path to location if found
    this.find_loc = function(uuid, loc) {
        loc = loc || this.root();

        if (loc.uuid() === uuid) {
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
    };

    // load location hierarchy
    this.load = function(locs) {
        this.root(new LocationModel({name: '_root', children: locs, can_edit: can_edit_root}, this));
        this.root().expanded(true);
    };
}

function LocationModel(data, root, depth) {
    var loc = this;

    this.name = ko.observable();
    this.type = ko.observable();
    this.uuid = ko.observable();
    this.is_archived = ko.observable();
    this.can_edit = ko.observable();
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
        this.is_archived(data.is_archived);
        this.can_edit(data.can_edit);
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
            return (top_level ? 'No locations created in this project yet' : 'No child locations inside ' + this.name());
        }, this);

    this.show_archive_action_button = ko.computed(function() {
        return !show_inactive || this.is_archived();
    }, this);

    this.load(data);

    this.new_location_tracking = function() {
        ga_track_event('Organization Structure', '+ New _______');
        return true;
    };
}
