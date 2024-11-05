hqDefine('locations/js/location_tree', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/alert_user',
    'analytix/js/google',
    'locations/js/search',
], function (
    $,
    ko,
    _,
    initialPageData,
    alertUser,
    googleAnalytics,
    locationUtils
) {
    function api_get_children(loc_uuid, show_inactive, callback) {
        var params = (loc_uuid ? {
            parent_id: loc_uuid,
        } : {});
        params.include_inactive = show_inactive;
        $.getJSON(initialPageData.get('api_root'), params, function (allData) {
            callback(allData.objects);
        });
    }

    function locationTreeViewModel(hierarchy, options) {
        // options should have property:
        //      "can_edit_root"

        var self = {};
        self.show_inactive = options.show_inactive;
        self.root = ko.observable();

        // TODO this should reference location type settings for domain
        self.location_types = $.map(hierarchy, function (e) {
            return {
                type: e[0],
                allowed_parents: e[1],
            };
        });

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

        // load location hierarchy
        self.load = function (locs) {
            self.root(locationModel({
                name: '_root',
                children: locs,
                can_edit: options.can_edit_root,
                expanded: true,
            }, self));
        };
        return self;
    }

    function locationSearchViewModel(treeModel, options) {
        // options should have property:
        //      "can_edit_root"

        var self = {};
        self.selected_location = ko.observable();
        self.selected_location_id = ko.observable();
        self.clearLocationSelection = locationUtils.clearLocationSelection.bind(self, treeModel);

        self.selected_location = ko.computed(function () {
            if (!self.selected_location_id()) {
                return;
            }
            return locationModel({
                uuid: self.selected_location_id(),
                can_edit: options.can_edit_root,
                is_archived: options.show_inactive,
            }, self);
        });

        self.lineage = ko.computed(function () {
            if (!self.selected_location()) {
                return;
            }
            $.ajax({
                type: 'GET',
                url: self.selected_location().loc_lineage_url(self.selected_location().uuid()),
                dataType: 'json',
                error: 'error',
                success: function (response) {
                    treeModel.root(self.expandTree(response.lineage));
                }.bind(self),
            });
        });

        self.expandTree = function (lineage) {
            var child, level;
            lineage.forEach(function (location, idx) {
                var data = {
                    name: location.name,
                    location_type: location.location_type,
                    uuid: location.location_id,
                    is_archived: location.is_archived,
                    can_edit: options.can_edit_root,
                    children: child,
                    expanded: child ? 'semi' : false,
                    children_status: 'semi_loaded',
                };
                level = locationModel(data, treeModel, lineage.length - idx - 1);
                child = Array.of(Object.assign({}, data));
            });
            var root_children = [];
            treeModel.root().children().forEach(function (location) {
                if (location.name() === child[0].name) {
                    root_children.push(child[0]);
                } else {
                    var data = {
                        can_edit: options.can_edit_root,
                        is_archived: location.is_archived(),
                        location_type: location.type(),
                        name: location.name(),
                        uuid: location.uuid(),
                    };
                    root_children.push(data);
                }
            });

            level = locationModel({
                name: '_root',
                children: root_children,
                can_edit: options.can_edit_root,
                expanded: 'semi',
            }, treeModel);
            return level;
        };
        return self;
    }

    function locationModel(data, root, depth) {
        var self = {};

        self.name = ko.observable();
        self.type = ko.observable();
        self.uuid = ko.observable();
        self.is_archived = ko.observable();
        self.can_edit = ko.observable();
        self.children = ko.observableArray();
        self.depth = depth || 0;
        self.children_status = ko.observable('not_loaded');
        self.expanded = ko.observable(false);

        self.reloadLocationSearchSelect = locationUtils.reloadLocationSearchSelect;
        self.clearLocationSelection = locationUtils.clearLocationSelection.bind(self, root);

        self.expanded.subscribe(function (val) {
            if (val === true && (self.children_status() === 'not_loaded' || self.children_status() === 'semi_loaded')) {
                self.load_children_async();
            }
        }, self);

        self.toggle = function () {
            if (self.expanded() === 'semi') {
                self.expanded(self.can_have_children());
            } else {
                self.expanded(!self.expanded() && self.can_have_children());
            }
        };

        self.load = function (data) {
            self.name(data.name);
            self.type(data.location_type);
            self.uuid(data.uuid);
            self.is_archived(data.is_archived);
            self.can_edit(data.can_edit);
            self.expanded(data.expanded);

            if (data.children_status !== null && data.children_status !== undefined) {
                self.children_status(data.children_status);
            }
            if (data.children !== null) {
                self.set_children(data.children);
            }
        };

        self.set_children = function (children) {
            var sortedChildren = [];
            if (children) {
                sortedChildren = _.sortBy(children, function (e) {
                    return e.name;
                });
            }

            if (self.children().length > 0 && self.name() !== "_root") {
                for (var child_idx = 0; child_idx < sortedChildren.length; child_idx++) {
                    if (sortedChildren[child_idx].name === self.children()[0].name()) {
                        sortedChildren.splice(child_idx, 1);
                        break;
                    }
                }

                var model_children = $.map(sortedChildren, function (e) {
                    return locationModel(e, root, self.depth + 1);
                });
                model_children.unshift(self.children()[0]);
                self.children(model_children);
            } else {
                self.children($.map(sortedChildren, function (e) {
                    return locationModel(e, root, self.depth + 1);
                }));
            }

            if (self.expanded() === true) {
                self.children_status('loaded');
            } else if (self.expanded() === 'semi') {
                self.children_status('semi_loaded');
            }
        };

        self.load_children_async = function (callback) {
            self.children_status('loading');
            api_get_children(self.uuid(), root.show_inactive, function (resp) {
                self.set_children(resp);
                if (callback) {
                    callback(self);
                }
            });
        };

        self.allowed_child_types = function () {
            var loc = self;
            var types = [];
            $.each(root.location_types, function (i, loc_type) {
                $.each(loc_type.allowed_parents, function (i, parent_type) {
                    if (loc.type() === parent_type) {
                        types.push(loc_type.type);
                    }
                });
            });
            return types;
        };

        self.can_have_children = ko.computed(function () {
            return (self.allowed_child_types().length > 0);
        }, self);

        self.allowed_child_type = function () {
            var types = self.allowed_child_types();
            return (types.length === 1 ? types[0] : null);
        };

        self.new_child_caption = ko.computed(function () {
            var child_type = self.allowed_child_type();
            var top_level = (self.name() === '_root');
            return 'New ' + (child_type || 'location') + (top_level ? ' at top level' : ' in ' + self.name() + ' ' + self.type());
        }, self);

        self.no_children_caption = ko.computed(function () {
            var top_level = (self.name() === '_root');

            // TODO replace 'location' with proper type as applicable (what about pluralization?)
            return (top_level ? 'No locations created in this project yet' : 'No child locations inside ' + self.name());
        }, self);

        self.show_archive_action_button = ko.computed(function () {
            return !root.show_inactive || self.is_archived();
        }, self);

        self.load(data);

        self.new_location_tracking = function () {
            googleAnalytics.track.event('Organization Structure', '+ New _______');
            return true;
        };

        self.remove_elements_after_action = function (button) {
            $(button).closest('.loc_section').remove();
        };

        self.archive_success_message = _.template(gettext("You have successfully archived the location <%-name%>"));

        self.delete_success_message = _.template(gettext(
            "You have successfully deleted the location <%-name%> and all of its child locations"
        ));

        self.delete_error_message = _.template(gettext("An error occurred while deleting your location. If the problem persists, please report an issue"));

        self.loc_archive_url = function (loc_id) {
            return initialPageData.reverse('archive_location', loc_id);
        };

        self.loc_unarchive_url = function (loc_id) {
            return initialPageData.reverse('unarchive_location', loc_id);
        };

        self.loc_delete_url = function (loc_id) {
            return initialPageData.reverse('delete_location', loc_id, loc_id);
        };

        self.loc_lineage_url = function (loc_id) {
            return initialPageData.reverse('location_lineage', loc_id);
        };

        self.loc_descendant_url = function (loc_id) {
            return initialPageData.reverse('location_descendants_count', loc_id);
        };

        self.loc_edit_url = function (loc_id, urlName) {
            urlName = urlName || 'edit_location';
            return initialPageData.reverse(urlName, loc_id);
        };

        self.new_loc_url = function () {
            return initialPageData.reverse('create_location');
        };

        self.location_search_url = function () {
            return initialPageData.reverse('location_search_url');
        };

        self.archive_loc = function (button, name, loc_id) {
            var archive_location_modal = $('#archive-location-modal')[0];

            function archive_fn() {
                $(button).disableButton();
                $.ajax({
                    type: 'POST',
                    url: self.loc_archive_url(loc_id),
                    dataType: 'json',
                    error: 'error',
                    success: function () {
                        alertUser.alert_user(self.archive_success_message({
                            "name": name,
                        }), "success");
                        self.remove_elements_after_action(button);
                        locationUtils.reloadLocationSearchSelect();
                    },
                });
                $(archive_location_modal).modal('hide');
                googleAnalytics.track.event('Organization Structure', 'Archive');
            }

            var modal_context = {
                "name": name,
                "loc_id": loc_id,
                "archive_fn": archive_fn,
            };
            ko.cleanNode(archive_location_modal);
            $(archive_location_modal).koApplyBindings(modal_context);
            $(archive_location_modal).modal('show');
        };

        self.unarchive_loc = function (button, loc_id) {
            $(button).disableButton();
            $.ajax({
                type: 'POST',
                url: self.loc_unarchive_url(loc_id),
                dataType: 'json',
                error: 'error',
                success: function () {
                    self.remove_elements_after_action(button);
                    locationUtils.reloadLocationSearchSelect();
                },
            });
        };

        self.delete_loc = function (button, name, loc_id) {
            var delete_location_modal = $('#delete-location-modal')[0];
            var modal_context;

            function delete_fn() {
                if (modal_context.count === parseInt(modal_context.signOff())) {
                    $(button).disableButton();

                    $.ajax({
                        type: 'DELETE',
                        url: self.loc_delete_url(loc_id),
                        dataType: 'json',
                        error: function () {
                            alertUser.alert_user(self.delete_error_message, "warning");
                            $(button).enableButton();
                        },
                        success: function (response) {
                            if (response.success) {
                                alertUser.alert_user(self.delete_success_message({
                                    "name": name,
                                }), "success");
                                self.remove_elements_after_action(button);
                                locationUtils.reloadLocationSearchSelect();
                            } else {
                                alertUser.alert_user(response.message, "warning");

                            }
                        },
                    });
                    $(delete_location_modal).modal('hide');
                    googleAnalytics.track.event('Organization Structure', 'Delete');
                }
            }

            $.ajax({
                type: 'GET',
                url: self.loc_descendant_url(loc_id),
                dataType: 'json',
                success: function (response) {
                    modal_context = {
                        "name": name,
                        "loc_id": loc_id,
                        "delete_fn": delete_fn,
                        "count": response.count,
                        "signOff": ko.observable(''),
                    };
                    ko.cleanNode(delete_location_modal);
                    ko.applyBindings(modal_context, delete_location_modal);
                    $(delete_location_modal).modal('show');
                },
            });
        };
        return self;
    }

    return {
        locationSearchViewModel: locationSearchViewModel,
        locationTreeViewModel: locationTreeViewModel,
        locationModel: locationModel,
    };
});
