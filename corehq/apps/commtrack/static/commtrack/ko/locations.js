
$(function() {
    var model = new LocationSettingsViewModel();
    $('#settings').submit(function() {
        return model.presubmit();
    });

    model.load(settings);
    ko.applyBindings(model, $('#settings').get(0));
});

function LocationSettingsViewModel() {
    this.loc_types = ko.observableArray();

    this.json_payload = ko.observable();

    this.loc_types_error = ko.observable();

    this.load = function(data) {
        this.loc_types($.map(data.loc_types, function(e) {
            return new LocationTypeModel(e);
        }));
    };

    var settings = this;

    this.remove_loctype = function(loc_type) {
        settings.loc_types.remove(loc_type);
    };

    this.new_loctype = function() {
        var new_loctype = new LocationTypeModel({}, this);
        new_loctype.onBind = function() {
            var $inp = $(this.$e).find('.loctype_name');
            $inp.focus();
            setTimeout(function() { $inp.select(); }, 0);
        };
        settings.loc_types.push(new_loctype);
    };

    this.validate = function() {
        this.loc_types_error(null);

        var that = this;
        var valid = true;

        $.each(this.loc_types(), function(i, e) {
                if (!e.validate()) {
                    valid = false;
                }
            });

        var top_level_loc = false;
        $.each(this.loc_types(), function(i, e) {
                if (e.allowed_parents().indexOf(undefined) != -1) {
                    top_level_loc = true;
                }
            });
        if (!top_level_loc) {
            this.loc_types_error('at least one location type must have "top level" as an allowed parent type');
            valid = false;
        }

        return valid;
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

function LocationTypeModel(data, root) {
    var name = data.name || '';
    var self = this;
    this.name = ko.observable(name);
    this.code = ko.observable(data.code || name);
    var code_autoset = this.name() == this.code();

    // sync code to name if it looks autoset
    this.name.subscribe(function (newValue) {
        if (code_autoset) {
            self.code(newValue);
        }
    });

    // clear autoset if we explicitly change the code
    this.code.subscribe(function (newValue) {
        self.name() != self.code();
        code_autoset = false;
    });

    var allowed_parents = data.allowed_parents || [];
    $.each(allowed_parents, function(i, e) {
        if (e === null) {
            allowed_parents[i] = undefined;
        }
    });
    if (allowed_parents.length == 0) {
        var last = root.loc_types.slice(-1)[0];
        allowed_parents = [last ? last.name() : undefined];
    }
    this.allowed_parents = ko.observableArray(allowed_parents);
    this.tracks_stock = ko.observable(!data.administrative);
    this.shares_cases = ko.observable(data.shares_cases);
    this.view_descendants = ko.observable(data.view_descendants);

    this.name_error = ko.observable();
    this.code_error = ko.observable();
    this.allowed_parents_error = ko.observable();

    this.validate = function() {
        this.name_error(null);
        this.allowed_parents_error(null);

        valid = true;

        if (!this.name()) {
            this.name_error('required');
            valid = false;
        }
        if (!this.code()) {
            this.code_error('required');
            valid = false;
        }
        if (this.allowed_parents().length == 0) {
            this.allowed_parents_error('choose at least one parent type');
            valid = false;
        }

        return valid;
    };

    this.to_json = function() {
        return {
            name: this.name(),
            code: this.code(),
            allowed_parents: this.allowed_parents(),
            administrative: !this.tracks_stock(),
            shares_cases: this.shares_cases() === true,
            view_descendants: this.view_descendants() === true
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
