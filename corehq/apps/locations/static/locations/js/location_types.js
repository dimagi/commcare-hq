/* globals _, ko, $ */

hqDefine('locations/js/location_types.js', function(){
    'use strict';
    var ROOT_LOCATION_ID = -1;

    function LocationSettingsViewModel(loc_types, commtrack_enabled) {
        var self = this;
        self.loc_types = ko.observableArray();
        self.loc_types($.map(loc_types, function(loc_type) {
            return new LocationTypeModel(loc_type, commtrack_enabled, self);
        }));

        self.json_payload = ko.observable();

        self.loc_types_error = ko.observable(false);
        self.advanced_mode = ko.observable(false);

        self.loc_type_options = function(loc_type) {
            return self.loc_types().filter(function(type) {
                return type.name !== loc_type.name;
            });
        };

        self.loc_types_by_id = function() {
            return _.reduce(self.loc_types(), function(memo, loc_type){
                memo[loc_type.pk] = loc_type;
                return memo;
            }, {});
        };

        self.loc_types_by_parent = function() {
            return _.reduce(self.loc_types(), function(memo, loc_type){
                var parent_type = loc_type.parent_type() || 0;
                if (memo[parent_type]){
                    memo[parent_type].push(loc_type);
                } else {
                    memo[parent_type] = [loc_type];
                }
                return memo;
            }, {});
        };

        self.types_by_index = function(location_types){
            return _.reduce(location_types, function(memo, loc_type){
                var level = loc_type.level();
                if (memo[level]){
                    memo[level].push(loc_type);
                } else {
                    memo[level] = [loc_type];
                }
                return memo;
            }, {}, self);
        };

        self.remove_loctype = function(loc_type) {
            self.loc_types.remove(loc_type);
        };

        self.new_loctype = function() {
            var parent_pk = (_.last(self.loc_types()) || {}).pk;
            var new_loctype = new LocationTypeModel({parent_type: parent_pk}, commtrack_enabled, self);
            new_loctype.onBind = function() {
                var $inp = $(self.$e).find('.loctype_name');
                $inp.focus();
                setTimeout(function() { $inp.select(); }, 0);
            };
            self.loc_types.push(new_loctype);
            ga_track_event('Organization Levels', 'New Organization Level');
        };

        self.validate = function() {
            self.loc_types_error(false);

            var valid = true;

            $.each(self.loc_types(), function(i, e) {
                if (!e.validate()) {
                    valid = false;
                }
            });

            // Make sure name and code are unique
            _.each({
                'name': 'duplicate_name_error',
                'code': 'duplicate_code_error',
            }, function (error_fn, field) {
                var counts_by_value = _.countBy(self.loc_types(), function (loc_type) {
                    return loc_type[field]();
                });
                var duplicates = [];
                _.each(counts_by_value, function (count, value) {
                    if (field === 'code' && value === ''){
                        // exclude empty codes
                        // if code is empty, the backend will autofill it as name
                        return;
                    }
                    if (count > 1) {
                        duplicates.push(value);
                        valid = false;
                    }
                });
                _.each(self.loc_types(), function (loc_type) {
                    loc_type[error_fn](false);
                    if (_.contains(duplicates, loc_type[field]())) {
                        loc_type[error_fn](true);
                    }
                });
            });

            var top_level_loc = false;
            $.each(self.loc_types(), function(i, e) {
                if (!e.parent_type()) {
                    top_level_loc = true;
                }
            });
            if (self.loc_types().length && !top_level_loc) {
                self.loc_types_error(true);
                valid = false;
            }
            if (self.has_cycles()) {
                self.loc_types_error(true);
                valid = false;
            }
            return valid;
        };

        self.has_cycles = function() {
            var loc_type_parents = {};
            $.each(self.loc_types(), function(i, loc_type) {
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
            for (var i = 0; i < self.loc_types().length; i++) {
                var visited = [],
                    loc_type = self.loc_types()[i].pk;
                if (already_visited(loc_type, visited)) {
                    return true;
                }
            }
            return false;
        };

        self.presubmit = function() {
            if (!self.validate()) {
                return false;
            }

            var payload = self.to_json();
            self.json_payload(JSON.stringify(payload));
            return true;
        };

        self.to_json = function() {
            return {
                loc_types: $.map(self.loc_types(), function(e) { return e.to_json(); }),
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

    function LocationTypeModel(loc_type, commtrack_enabled, view_model) {
        var self = this;
        var name = loc_type.name || '';
        self.pk = loc_type.pk || get_fake_pk();
        self.name = ko.observable(name);

        self.parent_type = ko.observable(loc_type.parent_type);
        self.tracks_stock = ko.observable(!loc_type.administrative);
        self.shares_cases = ko.observable(loc_type.shares_cases);
        self.view_descendants = ko.observable(loc_type.view_descendants);
        self.code = ko.observable(loc_type.code || '');
        self.expand_from = ko.observable(loc_type.expand_from_root ? ROOT_LOCATION_ID : loc_type.expand_from);
        self.expand_to = ko.observable(loc_type.expand_to);
        self.include_without_expanding = ko.observable(loc_type.include_without_expanding);

        self.view = view_model;

        self.name_error = ko.observable(false);
        self.duplicate_name_error = ko.observable(false);
        self.duplicate_code_error = ko.observable(false);

        self.validate = function() {
            self.name_error(false);
            if (!self.name()) {
                self.name_error(true);
                return false;
            }
            return true;
        };

        self.children = function(){
            var all_children = [self],
                to_check = [self];
            if (!self.view.has_cycles()){
                while (to_check.length > 0){
                    var current_loc = to_check.pop(),
                        children = self.view.loc_types_by_parent()[current_loc.pk];
                    if (children){
                        children.forEach(function(child){
                            all_children.push(child);
                            if (self.view.loc_types_by_parent()[child.pk]){
                                to_check.push(child);
                            }
                        }, self);
                    }
                }
            }
            return all_children;
        };

        self.parents = function(){
            var parents = [],
                to_check = [self];
            if (!self.view.has_cycles()) {
                while (to_check.length > 0){
                    var current_loc = to_check.pop(),
                        parent_type = current_loc.parent_type();
                    if (parent_type && self.view.loc_types_by_id()[parent_type]){
                        var parent = self.view.loc_types_by_id()[parent_type];
                        parents.push(parent);
                        if (parent.parent_type()){
                            to_check.push(parent);
                        }
                    }
                }
            }
            return parents;
        };

        self.level = function(){
            // Count the number of parents
            return self.parents().length;
        };

        self.compiled_name = function(){
            // Shows all types that have the same level as this one "type1 | type2"
            var compiled_name = "",
                location_types_same_level = self.view.types_by_index(self.view.loc_types())[self.level()];

            location_types_same_level.forEach(function(location_type, index){
                compiled_name += location_type.name();
                if (index !== location_types_same_level.length - 1){
                    compiled_name += " | ";
                }
            });
            return compiled_name;
        };

        self.expand_from_options = function() {
            // traverse all locations upwards, include a root option
            var root_type = new LocationTypeModel(
                {name: "root", pk: ROOT_LOCATION_ID},
                commtrack_enabled, this
            ),
                parents = self.parents();
            parents.push(root_type);
            return parents.reverse();
        };

        self.expand_to_options = function(){
            // display all locations with the same index as being on the same level
            var children = self.children(),
                children_same_levels = self.view.types_by_index(children),
                children_to_return = [];
            for (var level in children_same_levels){
                // Only display a single child at each level
                var child_to_add = children_same_levels[level][0];
                children_to_return.push(new LocationTypeModel({
                    name: child_to_add.compiled_name(),
                    pk: child_to_add.pk,
                }, false, self.view));
            }
            return {
                children: children_to_return.slice(0, children_to_return.length - 1),
                leaf: children_to_return[children_to_return.length - 1],
            };
        };

        self.include_without_expanding_options = function(){
            if (self.expand_from() !== ROOT_LOCATION_ID){
                var options = self.parents().reverse();
                options.push(self);
                return options;
            } else {
                return [];
            }
        };

        self.to_json = function() {
            return {
                pk: self.pk,
                name: self.name(),
                parent_type: self.parent_type() || null,
                administrative: commtrack_enabled ? !self.tracks_stock() : true,
                shares_cases: self.shares_cases() === true,
                view_descendants: self.view_descendants() === true,
                code: self.code().trim() || '',
                expand_from: (self.expand_from() !== -1 ? self.expand_from() : null) || null,
                expand_from_root: self.expand_from() === ROOT_LOCATION_ID,
                expand_to: self.expand_to() || null,
                include_without_expanding: self.include_without_expanding() || null,
            };
        };
    }
    return {
        'LocationSettingsViewModel': LocationSettingsViewModel,
        'LocationTypeModel': LocationTypeModel,
    };
});
