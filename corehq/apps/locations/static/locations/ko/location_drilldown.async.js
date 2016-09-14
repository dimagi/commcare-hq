/* globals LOAD_LOCS_URL, REQUIRED */

function api_get_children(loc_uuid, callback) {
    var params = (loc_uuid ? {parent_id: loc_uuid} : {});
    $('#loc_ajax').show().removeClass('hide');
    $.getJSON(LOAD_LOCS_URL, params, function(allData) {
        $('#loc_ajax').hide().addClass('hide');
        callback(allData.objects);
    });
}

function LocationSelectViewModel(hierarchy, default_caption, auto_drill, loc_filter, func, show_location_filter) {
    var model = this;

    this.default_caption = default_caption || 'All';
    this.auto_drill = (_.isBoolean(auto_drill) ? auto_drill : true);
    this.loc_filter = loc_filter || function(loc) { return true; };
    this.func = typeof func !== 'undefined' ? func : LocationModel;
    this.show_location_filter = ko.observable((typeof show_location_filter !== 'undefined') ? show_location_filter : 'y');

    this.root = ko.observable();
    this.selected_path = ko.observableArray();

    this.location_types = $.map(hierarchy, function(e) {
        return {type: e[0], allowed_parents: e[1]};
    });

    this.show_location_filter_bool = ko.computed(function() {
        return model.show_location_filter() === 'y';
    });

    // currently selected location in the tree (or null)
    this.selected_location = ko.computed(function() {
        for (var i = this.selected_path().length - 1; i >= 0; i--) {
            var loc = this.selected_path()[i];
            if (loc.selected_is_valid()) {
                return loc.selected_child();
            }
        }
        return null;
    }, this);
    // uuid of currently selected location (or null)
    this.selected_locid = ko.computed(function() {
        if(!model.show_location_filter_bool()) {
            return null;
        }
        return this.selected_location() ? this.selected_location().uuid() : null;
    }, this);

    // add a new level of drill-down to the tree
    this.path_push = function(loc) {
        if (this.selected_path().length !== this.location_types.length && this.selected_path.indexOf(loc) === -1) {
            this.selected_path.push(loc);
            if (this.auto_drill && loc.num_children() === 1) {
                loc.selected_child(loc.get_child(0));
            }
        }
    };

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

    // load location hierarchy and set initial path
    this.load = function(locs, selected) {
        this.root(new model.func({name: '_root', children: locs}, this));
        this.path_push(this.root());

        if (selected) {
            // this relies on the hierarchy of the selected location being pre-populated
            // in the initial locations set from the server (i.e., no location of the
            // pre-selected location's lineage is loaded asynchronously
            var sel_path = this.find_loc(selected);
            if (sel_path) {
                for (var i = 1; i < sel_path.length; i++) {
                    sel_path[i - 1].selected_child(sel_path[i]);
                }
            }
        }
    };
}

function LocationModel(data, root, depth, func, withAllOption) {
    var loc = this;

    this.name = ko.observable();
    this.type = ko.observable();
    this.uuid = ko.observable();
    this.can_edit = ko.observable();
    this.children = ko.observableArray();
    this.depth = depth || 0;
    this.children_loaded = false;
    this.func = typeof func !== 'undefined' ? func : LocationModel;
    this.withAllOption = typeof withAllOption !== 'undefined' ? withAllOption : true;

    this.children_are_editable = function() {
        return _.every(this.children(), function(child) {
            return child.name() === '_all' || child.can_edit();
        });
    };

    this.display_name = ko.computed(function() {
        return this.name() === '_all' ? root.default_caption : this.name();
    }, this);

    this.selected_child = ko.observable();
    // when a location is selected, update the drill-down tree
    this.selected_child.subscribe(function(val) {
        if (!val) {
            return;
        }

        var removed = root.selected_path.splice(val.depth, 99);
        $.each(removed, function(i, e) {
            // reset so dropdown for loc will default to 'all' if shown again
            e.selected_child(null);
        });

        var post_children_loaded = function(parent) {
            if (parent.num_children()) {
                root.path_push(parent);
            }
        };

        if (!!val.uuid() && !val.children_loaded) {
            val.load_children_async(post_children_loaded);
        } else {
            post_children_loaded(val);
        }
    }, this);
    this.selected_is_valid = ko.computed(function() {
        return this.selected_child() && this.selected_child().name() !== '_all';
    }, this);

    // helpers to account for the 'all' meta-entry
    this.num_children = ko.computed(function() {
        var length = this.children().length;
        if (this.withAllOption && length !== 0) {
            length -= 1;
        }
        return length;
    }, this);
    this.get_child = function(i) {
        return this.children()[i + 1];
    };

    this.load = function(data) {
        this.name(data.name);
        this.type(data.location_type);
        this.uuid(data.uuid);
        this.can_edit(_.isBoolean(data.can_edit) ? data.can_edit : true);
        if (data.children) {
            this.set_children(data.children);
        }
    };

    this.set_children = function(data) {
        var children = [];
        if (data) {
            children = _.sortBy(data, function(e) { return e.name; });

            //'all choices' meta-entry; annoying that we have to stuff this in
            //the children list, but all my attempts to make computed observables
            //based of children() caused infinite loops.
            if(loc.withAllOption || (!loc.withAllOption && loc.depth > REQUIRED))
                children.splice(0, 0, {name: '_all'});
        }
        this.children($.map(children, function(e) {
            var child = new loc.func(e, root, loc.depth + 1);
            return (child.filter() ? child : null);
        }));
        this.children_loaded = true;
    };

    this.load_children_async = function(callback) {
        api_get_children(this.uuid(), function(resp) {
            loc.set_children(resp);
            callback(loc);
        });
    };

    //warning: duplicate code with location_tree.async.js
    this.allowed_child_types = ko.computed(function() {
        var loc = this;
        var types = [];
        $.each(root.location_types, function(i, loc_type) {
            $.each(loc_type.allowed_parents, function(i, parent_type) {
                if (loc.type() === parent_type ||
                    (loc.type() === undefined && parent_type === null)) {
                    types.push(loc_type.type);
                }
            });
        });
        return types;
    }, this);

    this.can_have_children = ko.computed(function() {
        return (this.allowed_child_types().length > 0);
    }, this);

    this.filter = function() {
        return this.name() === '_all' || root.loc_filter(this);
    };

    this.can_edit_children = function() {
        // Are there more than one editable options?
        return this.children().filter(function(child) {
            return (child.name() !== '_all' && child.can_edit());
        }).length > 1;
    };

    this.load(data);
}
