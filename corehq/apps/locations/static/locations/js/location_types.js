'use strict';
hqDefine('locations/js/location_types', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'analytix/js/google',
    'select2/dist/js/select2.full.min',
    'hqwebapp/js/bootstrap5/hq.helpers',
    'commcarehq',
], function (
    $,
    ko,
    _,
    initialPageData,
    googleAnalytics
) {
    var ROOT_LOCATION_ID = -1;

    function locationSettingsViewModel(locTypes, commtrackEnabled) {
        var self = {};
        self.loc_types = ko.observableArray();
        self.loc_types($.map(locTypes, function (locType) {
            return locationTypeModel(locType, commtrackEnabled, self);
        }));

        self.json_payload = ko.observable();

        self.loc_types_error = ko.observable(false);
        self.advanced_mode = ko.observable(false);

        self.loc_type_options = function (locType) {
            return self.loc_types().filter(function (type) {
                return type.name !== locType.name;
            });
        };

        self.loc_types_by_id = function () {
            return _.reduce(self.loc_types(), function (memo, locType) {
                memo[locType.pk] = locType;
                return memo;
            }, {});
        };

        self.loc_types_by_parent = function () {
            return _.reduce(self.loc_types(), function (memo, locType) {
                var parentType = locType.parent_type() || 0;
                if (memo[parentType]) {
                    memo[parentType].push(locType);
                } else {
                    memo[parentType] = [locType];
                }
                return memo;
            }, {});
        };

        self.types_by_index = function (locationTypes) {
            return _.reduce(locationTypes, function (memo, locType) {
                var level = locType.level();
                if (memo[level]) {
                    memo[level].push(locType);
                } else {
                    memo[level] = [locType];
                }
                return memo;
            }, {}, self);
        };

        self.remove_loctype = function (locType) {
            self.loc_types.remove(locType);
        };

        self.new_loctype = function () {
            var parentPK = (_.last(self.loc_types()) || {}).pk;
            var newLocType = locationTypeModel({parent_type: parentPK}, commtrackEnabled, self);
            newLocType.onBind = function () {
                var $inp = $(self.$e).find('.loctype_name');
                $inp.focus();
                setTimeout(function () { $inp.select(); }, 0);
            };
            self.loc_types.push(newLocType);
            $(".include-only").last().select2();
            googleAnalytics.track.event('Organization Levels', 'New Organization Level');
        };

        self.validate = function () {
            self.loc_types_error(false);

            var valid = true;

            $.each(self.loc_types(), function (i, e) {
                if (!e.validate()) {
                    valid = false;
                }
            });

            // Make sure name and code are unique
            _.each({
                'name': 'duplicate_name_error',
                'code': 'duplicate_code_error',
            }, function (errorFn, field) {
                var countsByValue = _.countBy(self.loc_types(), function (locType) {
                    return locType[field]();
                });
                var duplicates = [];
                _.each(countsByValue, function (count, value) {
                    if (field === 'code' && value === '') {
                        // exclude empty codes
                        // if code is empty, the backend will autofill it as name
                        return;
                    }
                    if (count > 1) {
                        duplicates.push(value);
                        valid = false;
                    }
                });
                _.each(self.loc_types(), function (locType) {
                    locType[errorFn](false);
                    if (_.contains(duplicates, locType[field]())) {
                        locType[errorFn](true);
                    }
                });
            });

            var topLevelLoc = false;
            $.each(self.loc_types(), function (i, e) {
                if (!e.parent_type()) {
                    topLevelLoc = true;
                }
            });
            if (self.loc_types().length && !topLevelLoc) {
                self.loc_types_error(true);
                valid = false;
            }
            if (self.has_cycles()) {
                self.loc_types_error(true);
                valid = false;
            }
            return valid;
        };

        self.has_cycles = function () {
            var locTypeParents = {};
            $.each(self.loc_types(), function (i, locType) {
                locTypeParents[locType.pk] = locType.parent_type();
            });

            var alreadyVisited = function (lt, visited) {
                if (visited.indexOf(lt) !== -1) {
                    return true;
                } else if (!locTypeParents[lt]) {
                    return false;
                } else {
                    visited.push(lt);
                    return alreadyVisited(locTypeParents[lt], visited);
                }
            };
            for (var i = 0; i < self.loc_types().length; i++) {
                var visited = [],
                    locType = self.loc_types()[i].pk;
                if (alreadyVisited(locType, visited)) {
                    return true;
                }
            }
            return false;
        };

        self.presubmit = function () {
            if (!self.validate()) {
                return false;
            }

            var payload = self.to_json();
            self.json_payload(JSON.stringify(payload));
            return true;
        };

        self.to_json = function () {
            return {
                loc_types: $.map(self.loc_types(), function (e) { return e.to_json(); }),
            };
        };
        return self;
    }

    // Make a fake pk to refer to this location type even if the name changes
    var getFakePK = function () {
        var counter = 0;
        return function () {
            counter ++;
            return "fake-pk-" + counter;
        };
    }();

    function locationTypeModel(locType, commtrackEnabled, viewModel) {
        var self = {};
        var name = locType.name || '';
        self.pk = locType.pk || getFakePK();
        self.name = ko.observable(name);

        self.parent_type = ko.observable(locType.parent_type);
        self.tracks_stock = ko.observable(!locType.administrative);
        self.shares_cases = ko.observable(locType.shares_cases);
        self.view_descendants = ko.observable(locType.view_descendants);
        self.code = ko.observable(locType.code || '');
        self.expand_from = ko.observable(locType.expand_from_root ? ROOT_LOCATION_ID : locType.expand_from);
        self.expand_to = ko.observable(locType.expand_to);
        self.expand_view_child_data_to = ko.observable(locType.expand_view_child_data_to);
        self.has_users_setting = ko.observable(locType.has_users_setting || locType.has_users_setting === undefined); // new loc types default to true
        self.actually_has_users = ko.observable(locType.actually_has_users);
        self.include_without_expanding = ko.observable(locType.include_without_expanding);
        self.include_only = ko.observableArray(locType.include_only || []);

        self.view = viewModel;

        self.name_error = ko.observable(false);
        self.duplicate_name_error = ko.observable(false);
        self.duplicate_code_error = ko.observable(false);

        self.validate = function () {
            self.name_error(false);
            if (!self.name()) {
                self.name_error(true);
                return false;
            }
            return true;
        };

        self.children = function () {
            var allChildren = [self],
                toCheck = [self];
            if (!self.view.has_cycles()) {
                const locTypesByParent = self.view.loc_types_by_parent();
                while (toCheck.length > 0) {
                    var currentLoc = toCheck.pop(),
                        children = locTypesByParent[currentLoc.pk];
                    if (children) {
                        children.forEach(function (child) {
                            allChildren.push(child);
                            if (locTypesByParent[child.pk]) {
                                toCheck.push(child);
                            }
                        }, self);
                    }
                }
            }
            return allChildren;
        };

        self.parents = function () {
            var parents = [],
                toCheck = [self];
            if (!self.view.has_cycles()) {
                while (toCheck.length > 0) {
                    var currentLoc = toCheck.pop(),
                        parentType = currentLoc.parent_type();
                    if (parentType && self.view.loc_types_by_id()[parentType]) {
                        var parent = self.view.loc_types_by_id()[parentType];
                        parents.push(parent);
                        if (parent.parent_type()) {
                            toCheck.push(parent);
                        }
                    }
                }
            }
            return parents;
        };

        self.level = function () {
            // Count the number of parents
            return self.parents().length;
        };

        self.compiled_name = function () {
            // Shows all types that have the same level as this one "type1 | type2"
            var compiledName = "",
                locationTypesSameLevel = self.view.types_by_index(self.view.loc_types())[self.level()];

            _.each(locationTypesSameLevel, function (locationType, index) {
                compiledName += locationType.name();
                if (index !== locationTypesSameLevel.length - 1) {
                    compiledName += " | ";
                }
            });
            return compiledName;
        };

        self.expand_from_options = function () {
            // traverse all locations upwards, include a root option
            var rootType = locationTypeModel(
                    {name: "root", pk: ROOT_LOCATION_ID},
                    commtrackEnabled, self
                ),
                parents = self.parents();
            parents.push(rootType);
            return parents.reverse();
        };

        self.expand_to_options = function () {
            // display all locations with the same index as being on the same level
            let locs = self.children();
            if (self.expand_from() && self.expand_from() !== ROOT_LOCATION_ID) {
                locs = self.view.loc_types_by_id()[self.expand_from()].children();
            }
            if (self.expand_from() && self.expand_from() === ROOT_LOCATION_ID) {
                locs = self.view.loc_types();
            }
            const levels = self.getLevels(locs);
            return {
                children: levels.slice(0, levels.length - 1),
                leaf: levels[levels.length - 1],
            };
        };

        self.child_loc_types = function () {
            const locs = self.children();
            const levels = self.getLevels(locs);
            levels.shift(); // not self
            return levels;
        };

        self.getLevels = function (locs) {
            const locsSameLevels = self.view.types_by_index(locs);
            const locsToReturn = [];
            for (const level in locsSameLevels) {
                // Only display a single child at each level
                const childToAdd = locsSameLevels[level][0];
                locsToReturn.push(locationTypeModel({
                    name: childToAdd.compiled_name(),
                    pk: childToAdd.pk,
                }, false, self.view));
            }
            return locsToReturn;

        };

        self.include_without_expanding_options = function () {
            if (self.expand_from() !== ROOT_LOCATION_ID) {
                var typesSameLevels = self.view.types_by_index(self.view.loc_types()),
                    levelsToReturn = [];
                for (var level in typesSameLevels) {
                    // Only display a single child at each level
                    var levelToAdd = typesSameLevels[level][0];
                    levelsToReturn.push(locationTypeModel({
                        name: levelToAdd.compiled_name(),
                        pk: levelToAdd.pk,
                    }, false, self.view));
                }
                return levelsToReturn;
            } else {
                return [];
            }
        };

        self.include_only_options = function () {
            return self.view.loc_types();
        };

        self.to_json = function () {
            return {
                pk: self.pk,
                name: self.name(),
                parent_type: self.parent_type() || null,
                administrative: commtrackEnabled ? !self.tracks_stock() : true,
                shares_cases: self.shares_cases() === true,
                view_descendants: self.view_descendants() === true,
                code: self.code().trim() || '',
                expand_from: (self.expand_from() !== -1 ? self.expand_from() : null) || null,
                expand_from_root: self.expand_from() === ROOT_LOCATION_ID,
                expand_to: self.expand_to() || null,
                expand_view_child_data_to: self.expand_view_child_data_to() || null,
                has_users: self.has_users_setting() === true,
                include_without_expanding: self.include_without_expanding() || null,
                include_only: self.include_only() || [],
            };
        };
        return self;
    }

    $(function () {
        var locTypes = initialPageData.get('location_types'),
            commtrackEnabled = initialPageData.get('commtrack_enabled'),
            model = locationSettingsViewModel(locTypes, commtrackEnabled);

        var warnBeforeUnload = function () {
            return gettext("You have unsaved changes.");
        };

        var $settings = $('#settings');
        if ($settings.length) {
            $settings.submit(function () {
                var valid = model.presubmit();
                if (valid) {
                    // Don't warn if they're leaving the page due to form submission
                    window.onbeforeunload = undefined;
                }
                return valid;
            });
            $settings.koApplyBindings(model);
        }

        $("form#settings").on("change input", function () {
            $(this).find(":submit").addClass("btn-primary").enableButton();
            window.onbeforeunload = warnBeforeUnload;
        });

        $("form#settings button").on("click", function () {
            $("form#settings").find(":submit").enableButton();
            window.onbeforeunload = warnBeforeUnload;
        });

        $(".include-only").select2();
    });

    return {
        'locationSettingsViewModel': locationSettingsViewModel,
        'locationTypeModel': locationTypeModel,
    };
});
