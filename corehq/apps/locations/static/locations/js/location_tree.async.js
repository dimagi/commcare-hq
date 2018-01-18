
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

function LocationSearchViewModel() {
    var model = this;
    this.selected_location = ko.observable();
    this.l__selected_location_id = ko.observable();

    this.selected_location_id = ko.computed(function () {
        if (!model.l__selected_location_id()) {
            return;
        }
        return (model.l__selected_location_id().split("l__")[1]);
    });

    this.selected_location = ko.computed(function() {
        return new LocationModel({uuid: model.selected_location_id(), can_edit: can_edit_root}, this);
    });

}

function LocationModel(data, root, depth) {
    var loc = this;

    this.name = ko.observable();
    this.type = ko.observable();
    this.uuid = ko.observable();
    this.is_archived = ko.observable();
    this.is_deleted = ko.observable();
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
        hqImport('analytix/js/google').track.event('Organization Structure', '+ New _______');
        return true;
    };

    archive_loc = function(button, name, loc_id) {
        var archive_location_modal = $('#archive-location-modal')[0];

        function archive_fn() {
            $(button).disableButton();
            $.ajax({
                type: 'POST',
                url: loc_archive_url(loc_id),
                dataType: 'json',
                error: 'error',
                success: function (response) {
                    alert_user(archive_success_message({"name": name}), "success");
                    $(button).removeSpinnerFromButton();
                    loc.is_archived(true);
                    remove_elements_after_action(button);
                }
            });
            $(archive_location_modal).modal('hide');
            hqImport('analytix/js/google').track.event('Organization Structure', 'Archive')
        }

        var modal_context = {
            "name": name,
            "loc_id": loc_id,
            "archive_fn": archive_fn
        };
        ko.cleanNode(archive_location_modal);
        $(archive_location_modal).koApplyBindings(modal_context);
        $(archive_location_modal).modal('show');
    };

    unarchive_loc = function(button, loc_id) {
        $(button).disableButton();
        $.ajax({
            type: 'POST',
            url: loc_unarchive_url(loc_id),
            dataType: 'json',
            error: 'error',
            success: function (response) {
                remove_elements_after_action(button);
            }
        });
    };

    delete_loc = function(button, name, loc_id) {
        var delete_location_modal = $('#delete-location-modal')[0];
        var modal_context;

        function delete_fn() {
            if (modal_context.count == modal_context.signOff()) {
                $(button).disableButton();

                $.ajax({
                    type: 'DELETE',
                    url: loc_delete_url(loc_id),
                    dataType: 'json',
                    error: function (response, status, error) {
                        alert_user(delete_error_message, "warning");
                        $(button).enableButton();
                    },
                    success: function (response) {
                        if (response.success){
                            alert_user(delete_success_message({"name": name}), "success");
                            $(button).removeSpinnerFromButton();
                            loc.is_deleted(true);
                            remove_elements_after_action(button);

                        }
                        else {
                            alert_user(response.message, "warning");

                        }
                    }
                });
                $(delete_location_modal).modal('hide');
                hqImport('analytix/js/google').track.event('Organization Structure', 'Delete')
            }
        }

        $.ajax({
            type: 'GET',
            url: loc_descendant_url(loc_id),
            dataType: 'json',
            success: function (response) {
                modal_context = {
                    "name": name,
                    "loc_id": loc_id,
                    "delete_fn": delete_fn,
                    "count": response.count,
                    "signOff": ko.observable('')
                };
                ko.cleanNode(delete_location_modal);
                ko.applyBindings(modal_context, delete_location_modal);
                $(delete_location_modal).modal('show');
            }
        });
    };
}
