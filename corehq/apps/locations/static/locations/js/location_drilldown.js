hqDefine('locations/js/location_drilldown', [
    'jquery',
    'knockout',
    'underscore',
], function(
    $,
    ko,
    _
) {
    function apiGetChildren(locUuid, callback, locUrl) {
        var params = (locUuid ? {parent_id: locUuid} : {});
        $('#loc_ajax').show().removeClass('hide');
        $.getJSON(locUrl, params, function(allData) {
            $('#loc_ajax').hide().addClass('hide');
            callback(allData.objects);
        });
    }

    function locationSelectViewModel(options) {
        var model = {};

        model.loc_url = options.loc_url;
        model.default_caption = options.default_caption || 'All';
        model.auto_drill = (_.isBoolean(options.auto_drill) ? options.auto_drill : true);
        model.loc_filter = options.loc_filter || function() { return true; };
        model.func = typeof options.func !== 'undefined' ? options.func : locationModel;
        model.show_location_filter = ko.observable((typeof options.show_location_filter !== 'undefined') ? options.show_location_filter : 'y');

        model.root = ko.observable();
        model.selected_path = ko.observableArray();

        model.location_types = $.map(options.hierarchy, function(e) {
            return {type: e[0], allowed_parents: e[1]};
        });
        // max allowed drilldown levels
        model.max_drill_depth = options.max_drill_depth || model.location_types.length;

        model.show_location_filter_bool = ko.computed(function() {
            return model.show_location_filter() === 'y';
        });

        // currently selected location in the tree (or null)
        model.selected_location = ko.computed(function() {
            for (var i = model.selected_path().length - 1; i >= 0; i--) {
                var loc = model.selected_path()[i];
                if (loc.selected_is_valid()) {
                    return loc.selected_child();
                }
            }
            return null;
        }, model);
        // uuid of currently selected location (or null)
        model.selected_locid = ko.computed(function() {
            if(!model.show_location_filter_bool()) {
                return null;
            }
            return model.selected_location() ? model.selected_location().uuid() : null;
        }, model);

        // add a new level of drill-down to the tree
        model.path_push = function(loc) {
            if (model.selected_path().length !== model.location_types.length &&
                model.selected_path.indexOf(loc) === -1 &&
                model.selected_path().length < model.max_drill_depth) {
                model.selected_path.push(loc);
                if (model.auto_drill && loc.num_children() === 1) {
                    loc.selected_child(loc.get_child(0));
                }
            }
        };

        // search for a location within the tree by uuid; return path to location if found
        model.find_loc = function(uuid, loc) {
            loc = loc || model.root();

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
        model.load = function(locs, selected) {
            model.root(new model.func({name: '_root', children: locs, auto_drill: model.auto_drill}, model, options.required));
            model.path_push(model.root());

            if (selected) {
                // this relies on the hierarchy of the selected location being pre-populated
                // in the initial locations set from the server (i.e., no location of the
                // pre-selected location's lineage is loaded asynchronously
                var selPath = model.find_loc(selected);
                if (selPath) {
                    for (var i = 1; i < selPath.length; i++) {
                        selPath[i - 1].selected_child(selPath[i]);
                    }
                }
            }
        };
        return model;
    }

    function locationModel(data, root, depth, func, withAllOption, requiredOption) {
        var loc = {};

        loc.name = ko.observable();
        loc.type = ko.observable();
        loc.uuid = ko.observable();
        loc.can_edit = ko.observable();
        loc.children = ko.observableArray();
        loc.depth = depth || 0;
        loc.children_loaded = false;
        loc.func = typeof func !== 'undefined' ? func : locationModel;
        loc.withAllOption = typeof withAllOption !== 'undefined' ? withAllOption : true;

        loc.auto_drill = data.auto_drill;

        loc.children_are_editable = function() {
            return _.every(loc.children(), function(child) {
                return child.name() === '_all' || child.can_edit();
            });
        };

        loc.display_name = ko.computed(function() {
            return loc.name() === '_all' ? root.default_caption : loc.name();
        }, loc);

        loc.selected_child = ko.observable();
        // when a location is selected, update the drill-down tree
        loc.selected_child.subscribe(function(val) {
            if (!val) {
                return;
            }

            var removed = root.selected_path.splice(val.depth, 99);
            $.each(removed, function(i, e) {
                // reset so dropdown for loc will default to 'all' if shown again
                e.selected_child(null);
            });

            var postChildrenLoaded = function(parent) {
                if (parent.num_children()) {
                    root.path_push(parent);
                }
            };

            if (!!val.uuid() && !val.children_loaded) {
                val.load_children_async(postChildrenLoaded);
            } else {
                postChildrenLoaded(val);
            }
        }, loc);
        loc.selected_is_valid = ko.computed(function() {
            return loc.selected_child() && loc.selected_child().name() !== '_all';
        }, loc);

        // helpers to account for the 'all' meta-entry
        loc.num_children = ko.computed(function() {
            var length = loc.children().length;
            if (loc.withAllOption && length !== 0) {
                length -= 1;
            }
            return length;
        }, loc);
        loc.get_child = function(i) {
            return loc.children()[i + 1];
        };

        loc.load = function(data) {
            loc.name(data.name);
            loc.type(data.location_type);
            loc.uuid(data.uuid);
            loc.can_edit(_.isBoolean(data.can_edit) ? data.can_edit : true);
            if (data.children) {
                loc.set_children(data.children);
            }
        };

        loc.set_children = function(data) {
            var children = [];
            if (data) {
                children = _.sortBy(data, function(e) { return e.name; });

                //'all choices' meta-entry; annoying that we have to stuff this in
                //the children list, but all my attempts to make computed observables
                //based of children() caused infinite loops.
                if(loc.withAllOption || (!loc.withAllOption && loc.depth > requiredOption))
                    children.splice(0, 0, {name: '_all', auto_drill: loc.auto_drill});
            }
            loc.children($.map(children, function(e) {
                e.auto_drill = loc.auto_drill;
                var child = new loc.func(e, root, loc.depth + 1);
                return (child.filter() ? child : null);
            }));
            loc.children_loaded = true;
        };

        loc.load_children_async = function(callback) {
            apiGetChildren(loc.uuid(), function(resp) {
                loc.set_children(resp);
                callback(loc);
            }, root.loc_url);
        };

        //warning: duplicate code with location_tree.async.js
        loc.allowed_child_types = ko.computed(function() {
            var types = [];
            $.each(root.location_types, function(i, locType) {
                $.each(locType.allowed_parents, function(i, parentType) {
                    if (loc.type() === parentType ||
                        (loc.type() === undefined && parentType === null)) {
                        types.push(locType.type);
                    }
                });
            });
            return types;
        }, loc);

        loc.can_have_children = ko.computed(function() {
            return (loc.allowed_child_types().length > 0);
        }, loc);

        loc.filter = function() {
            return loc.name() === '_all' || root.loc_filter(loc);
        };

        loc.can_edit_children = function() {
            // Are there more than one editable options?
            return loc.children().filter(function(child) {
                return ((!loc.auto_drill || child.name() !== '_all') && child.can_edit());
            }).length > 1;
        };

        loc.load(data);

        return loc;
    }

    return {
        locationSelectViewModel: locationSelectViewModel,
        locationModel: locationModel,
    };
});
