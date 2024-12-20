hqDefine('locations/js/location_drilldown', [
    'jquery',
    'knockout',
    'underscore',
], function (
    $,
    ko,
    _
) {
    function apiGetChildren(locUuid, callback, locUrl) {
        // Both B3 hide and B5 d-none are used to avoid needing to split this template.
        // When USE_BOOTSTRAP5 is removed, form-control can be removed.
        var params = (locUuid ? {parent_id: locUuid} : {});
        $('#loc_ajax').removeClass('hide d-none');
        $.getJSON(locUrl, params, function (allData) {
            $('#loc_ajax').addClass('hide d-none');
            callback(allData.objects);
        });
    }

    function locationSelectViewModel(options) {
        var self = {};

        self.loc_url = options.loc_url;
        self.default_caption = options.default_caption || 'All';
        self.auto_drill = (_.isBoolean(options.auto_drill) ? options.auto_drill : true);
        self.loc_filter = options.loc_filter || function () { return true; };
        self.func = typeof options.func !== 'undefined' ? options.func : locationModel;
        self.show_location_filter = ko.observable((typeof options.show_location_filter !== 'undefined') ? options.show_location_filter : 'y');

        self.root = ko.observable();
        self.selected_path = ko.observableArray();

        self.location_types = $.map(options.hierarchy, function (e) {
            return {type: e[0], allowed_parents: e[1]};
        });
        // max allowed drilldown levels
        self.max_drill_depth = options.max_drill_depth || self.location_types.length;

        self.show_location_filter_bool = ko.computed(function () {
            return self.show_location_filter() === 'y';
        });

        // currently selected location in the tree (or null)
        self.selected_location = ko.computed(function () {
            for (var i = self.selected_path().length - 1; i >= 0; i--) {
                var loc = self.selected_path()[i];
                if (loc.selected_is_valid()) {
                    return loc.selected_child();
                }
            }
            return null;
        }, self);
        // uuid of currently selected location (or null)
        self.selected_locid = ko.computed(function () {
            if (!self.show_location_filter_bool()) {
                return null;
            }
            return self.selected_location() ? self.selected_location().uuid() : null;
        }, self);

        // add a new level of drill-down to the tree
        self.path_push = function (loc) {
            if (self.selected_path().length !== self.location_types.length &&
                self.selected_path.indexOf(loc) === -1 &&
                self.selected_path().length < self.max_drill_depth) {
                self.selected_path.push(loc);
                if (self.auto_drill && loc.num_children() === 1) {
                    loc.selected_child(loc.get_child(0));
                }
            }
        };

        // search for a location within the tree by uuid; return path to location if found
        self.find_loc = function (uuid, loc) {
            loc = loc || self.root();

            if (loc.uuid() === uuid) {
                return [loc];
            } else {
                var path = null;
                $.each(loc.children(), function (i, e) {
                    var subpath = self.find_loc(uuid, e);
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
        self.load = function (locs, selected) {
            self.root(self.func({name: '_root', children: locs, auto_drill: self.auto_drill}, self, options.required));
            self.path_push(self.root());

            if (selected) {
                // this relies on the hierarchy of the selected location being pre-populated
                // in the initial locations set from the server (i.e., no location of the
                // pre-selected location's lineage is loaded asynchronously
                var selPath = self.find_loc(selected);
                if (selPath) {
                    for (var i = 1; i < selPath.length; i++) {
                        selPath[i - 1].selected_child(selPath[i]);
                    }
                }
            }
        };
        return self;
    }

    function locationModel(data, root, depth, func, withAllOption, requiredOption) {
        var self = {};

        self.name = ko.observable();
        self.type = ko.observable();
        self.uuid = ko.observable();
        self.can_edit = ko.observable();
        self.children = ko.observableArray();
        self.depth = depth || 0;
        self.children_loaded = false;
        self.func = typeof func !== 'undefined' ? func : locationModel;
        self.withAllOption = typeof withAllOption !== 'undefined' ? withAllOption : true;

        self.auto_drill = data.auto_drill;

        self.children_are_editable = function () {
            return _.every(self.children(), function (child) {
                return child.name() === '_all' || child.can_edit();
            });
        };

        self.display_name = ko.computed(function () {
            return self.name() === '_all' ? root.default_caption : self.name();
        }, self);

        self.selected_child = ko.observable();
        // when a location is selected, update the drill-down tree
        self.selected_child.subscribe(function (val) {
            if (!val) {
                return;
            }

            var removed = root.selected_path.splice(val.depth, 99);
            $.each(removed, function (i, e) {
                // reset so dropdown for loc will default to 'all' if shown again
                e.selected_child(null);
            });

            var postChildrenLoaded = function (parent) {
                if (parent.num_children()) {
                    root.path_push(parent);
                }
            };

            if (!!val.uuid() && !val.children_loaded) {
                val.load_children_async(postChildrenLoaded);
            } else {
                postChildrenLoaded(val);
            }
        }, self);
        self.selected_is_valid = ko.computed(function () {
            return self.selected_child() && self.selected_child().name() !== '_all';
        }, self);

        // helpers to account for the 'all' meta-entry
        self.num_children = ko.computed(function () {
            var length = self.children().length;
            if (self.withAllOption && length !== 0) {
                length -= 1;
            }
            return length;
        }, self);
        self.get_child = function (i) {
            return self.children()[i + 1];
        };

        self.load = function (data) {
            self.name(data.name);
            self.type(data.location_type);
            self.uuid(data.uuid);
            self.can_edit(_.isBoolean(data.can_edit) ? data.can_edit : true);
            if (data.children) {
                self.set_children(data.children);
            }
        };

        self.set_children = function (data) {
            var children = [];
            if (data) {
                children = _.sortBy(data, function (e) { return e.name; });

                //'all choices' meta-entry; annoying that we have to stuff this in
                //the children list, but all my attempts to make computed observables
                //based of children() caused infinite loops.
                if (self.withAllOption || (!self.withAllOption && self.depth > requiredOption)) {
                    children.splice(0, 0, {name: '_all', auto_drill: self.auto_drill});
                }
            }
            self.children($.map(children, function (e) {
                e.auto_drill = self.auto_drill;
                var child = self.func(e, root, self.depth + 1);
                return (child.filter() ? child : null);
            }));
            self.children_loaded = true;
        };

        self.load_children_async = function (callback) {
            apiGetChildren(self.uuid(), function (resp) {
                self.set_children(resp);
                callback(self);
            }, root.loc_url);
        };

        //warning: duplicate code with location_tree.async.js
        self.allowed_child_types = ko.computed(function () {
            var types = [];
            $.each(root.location_types, function (i, locType) {
                $.each(locType.allowed_parents, function (i, parentType) {
                    if (self.type() === parentType ||
                        (self.type() === undefined && parentType === null)) {
                        types.push(locType.type);
                    }
                });
            });
            return types;
        }, self);

        self.can_have_children = ko.computed(function () {
            return (self.allowed_child_types().length > 0);
        }, self);

        self.filter = function () {
            return self.name() === '_all' || root.loc_filter(self);
        };

        self.can_edit_children = function () {
            // Are there more than one editable options?
            return self.children().filter(function (child) {
                return ((!self.auto_drill || child.name() !== '_all') && child.can_edit());
            }).length > 1;
        };

        self.load(data);

        return self;
    }

    return {
        locationSelectViewModel: locationSelectViewModel,
        locationModel: locationModel,
    };
});
