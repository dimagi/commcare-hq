/* globals _, ko, $ */

var ROOT_LOCATION_ID = -1;

function LocationSettingsViewModel(loc_types, commtrack_enabled) {
    this.loc_types = ko.observableArray();
    this.loc_types($.map(loc_types, function(loc_type) {
        return new LocationTypeModel(loc_type, commtrack_enabled);
    }));

    var root_type = new LocationTypeModel({
        name: "root",
        pk: ROOT_LOCATION_ID,
    });

    this.json_payload = ko.observable();

    this.loc_types_error = ko.observable(false);
    this.advanced_mode = ko.observable(false);

    this.loc_type_options = function(loc_type) {
        return this.loc_types().filter(function(type) {
            return type.name !== loc_type.name;
        });
    };

    this.loc_types_by_id = _.reduce(this.loc_types(), function(memo, loc_type){
        memo[loc_type.pk] = loc_type;
        return memo;
    }, {});

    this.loc_types_by_parent = _.reduce(this.loc_types(), function(memo, loc_type){
        memo[loc_type.parent_type()] = loc_type;
        return memo;
    }, {});

    this.expand_from_options = function(loc_type) {
        // traverse all locations upwards, include a root option
        var parents = [],
            to_check = [loc_type];
        if (!this.has_cycles()) {
            while (to_check.length > 0){
                var current_loc = to_check.pop(),
                    parent_type = current_loc.parent_type();
                if (parent_type){
                    var parent = this.loc_types_by_id[parent_type];
                    parents.push(parent);
                    if (parent.parent_type()){
                        to_check.push(parent);
                    }
                }
            }
        }
        parents.push(root_type);
        return parents.reverse();
    };

    this.expand_to_options = function(loc_type) {
        // from us, go down the tree, extract the last one so we can use it as the default
        var children = [loc_type],
            to_check = [loc_type];

        if (!this.has_cycles()){
            while (to_check.length > 0){
                var current_loc = to_check.pop(),
                    child = this.loc_types_by_parent[current_loc.pk];
                if (child){
                    children.push(child);
                    if (this.loc_types_by_parent[child.pk]){
                        to_check.push(child);
                    }
                }
            }
        }
        return {
            children: children.slice(0, children.length - 1),
            leaf: children[children.length - 1],
        };
    };

    var settings = this;

    this.remove_loctype = function(loc_type) {
        settings.loc_types.remove(loc_type);
    };

    this.new_loctype = function() {
        var parent_pk = (_.last(settings.loc_types()) || {}).pk;
        var new_loctype = new LocationTypeModel({parent_type: parent_pk}, commtrack_enabled);
        new_loctype.onBind = function() {
            var $inp = $(this.$e).find('.loctype_name');
            $inp.focus();
            setTimeout(function() { $inp.select(); }, 0);
        };
        settings.loc_types.push(new_loctype);
        ga_track_event('Organization Levels', 'New Organization Level');
    };

    this.validate = function() {
        this.loc_types_error(false);

        var valid = true;

        $.each(this.loc_types(), function(i, e) {
            if (!e.validate()) {
                valid = false;
            }
        });

        var top_level_loc = false;
        $.each(this.loc_types(), function(i, e) {
            if (!e.parent_type()) {
                top_level_loc = true;
            }
        });
        if (this.loc_types().length && !top_level_loc) {
            this.loc_types_error(true);
            valid = false;
        }
        if (this.has_cycles()) {
            this.loc_types_error(true);
            valid = false;
        }
        return valid;
    };

    this.has_cycles = function() {
        var loc_type_parents = {};
        $.each(this.loc_types(), function(i, loc_type) {
            loc_type_parents[loc_type.pk] = loc_type.parent_type();
        });

        var already_visited = function(lt, visited) {
            if (visited.indexOf(lt) !== -1) {
                return true;
            } else if (!loc_type_parents[lt]) {
                return false;
            } else {
                visited.push(lt);
                return already_visited(loc_type_parents[lt], visited);
            }
        };
        for (var i = 0; i < this.loc_types().length; i++) {
            var visited = [],
                loc_type = this.loc_types()[i].pk;
            if (already_visited(loc_type, visited)) {
                return true;
            }
        }
        return false;
    };

    this.presubmit = function() {
        if (!this.validate()) {
            return false;
        }

        var payload = this.to_json();
        this.json_payload(JSON.stringify(payload));
        return true;
    };

    this.to_json = function() {
        return {
            loc_types: $.map(this.loc_types(), function(e) { return e.to_json(); }),
        };
    };
}

// Make a fake pk to refer to this location type even if the name changes
var get_fake_pk = function () {
    var counter = 0;
    return function() {
        counter ++;
        return "fake-pk-" + counter;
    };
}();

function LocationTypeModel(loc_type, commtrack_enabled) {
    var name = loc_type.name || '';
    this.pk = loc_type.pk || get_fake_pk();
    this.name = ko.observable(name);

    this.parent_type = ko.observable(loc_type.parent_type);
    this.tracks_stock = ko.observable(!loc_type.administrative);
    this.shares_cases = ko.observable(loc_type.shares_cases);
    this.view_descendants = ko.observable(loc_type.view_descendants);
    this.code = ko.observable(loc_type.code || '');
    this.expand_from = ko.observable(loc_type.expand_from_root ? ROOT_LOCATION_ID : loc_type.expand_from);
    this.expand_to = ko.observable(loc_type.expand_to);

    this.name_error = ko.observable(false);

    this.validate = function() {
        this.name_error(false);
        if (!this.name()) {
            this.name_error(true);
            return false;
        }
        return true;
    };

    this.to_json = function() {
        return {
            pk: this.pk,
            name: this.name(),
            parent_type: this.parent_type() || null,
            administrative: commtrack_enabled ? !this.tracks_stock() : true,
            shares_cases: this.shares_cases() === true,
            view_descendants: this.view_descendants() === true,
            code: this.code().trim() || '',
            expand_from: (this.expand_from() !== -1 ? this.expand_from() : null) || null,
            expand_from_root: this.expand_from() === ROOT_LOCATION_ID,
            expand_to: this.expand_to() || null,
        };
    };
}

// TODO move to shared library
ko.bindingHandlers.bind_element = {
    init: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var field = valueAccessor() || '$e';
        if (viewModel[field]) {
            console.warning('warning: element already bound');
            return;
        }
        viewModel[field] = element;
        if (viewModel.onBind) {
            viewModel.onBind(bindingContext);
        }
    },
};
