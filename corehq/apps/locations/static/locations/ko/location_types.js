function LocationSettingsViewModel(loc_types, commtrack_enabled) {
    this.loc_types = ko.observableArray();
    this.loc_types($.map(loc_types, function(loc_type) {
        return new LocationTypeModel(loc_type, commtrack_enabled);
    }));

    this.json_payload = ko.observable();

    this.loc_types_error = ko.observable(false);
    this.advanced_mode = ko.observable(false);

    this.loc_type_options = function(loc_type) {
        return this.loc_types().filter(function(type) {
            return type.name !== loc_type.name;
        });
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
    };

    this.validate = function() {
        this.loc_types_error(false);

        var that = this;
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
            var visited = [];
                loc_type = this.loc_types()[i].pk;
            if (already_visited(loc_type, visited)) {
                return true;
            }
        }
    };

    this.presubmit = function() {
        if (!this.validate()) {
            return false;
        }

        payload = this.to_json();
        this.json_payload(JSON.stringify(payload));
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
    var self = this;
    this.pk = loc_type.pk || get_fake_pk();
    this.name = ko.observable(name);

    this.parent_type = ko.observable(loc_type.parent_type);
    this.tracks_stock = ko.observable(!loc_type.administrative);
    this.shares_cases = ko.observable(loc_type.shares_cases);
    this.view_descendants = ko.observable(loc_type.view_descendants);
    this.code = ko.observable(loc_type.code || '');

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
            code: this.code().trim() || ''
        };
    };
}

// TODO move to shared library
ko.bindingHandlers.bind_element = {
    init: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var field = valueAccessor() || '$e';
        if (viewModel[field]) {
            console.log('warning: element already bound');
            return;
        }
        viewModel[field] = element;
        if (viewModel.onBind) {
            viewModel.onBind(bindingContext);
        }
    }
};
