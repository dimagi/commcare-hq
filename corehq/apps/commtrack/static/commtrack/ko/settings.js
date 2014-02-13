
$(function() {
        
        var model = new CommtrackSettingsViewModel();
        $('#settings').submit(function() {
                return model.presubmit();
            });

        model.load(settings);
        ko.applyBindings(model);

    });

function CommtrackSettingsViewModel() {
    this.keyword = ko.observable();
    this.actions = ko.observableArray();
    this.loc_types = ko.observableArray();
    this.requisition_config = ko.observable();
    this.openlmis_config = ko.observable();

    this.json_payload = ko.observable();

    this.keyword_error = ko.observable();
    this.loc_types_error = ko.observable();

    // TODO: sort out possibly removing this redundant declaration in js
    this.action_types = [
        {label: 'Stock on hand', value: 'stockonhand'},
        {label: 'Receipts', value: 'receipts'},
        {label: 'Consumption', value: 'consumption'},
        {label: 'Stock out', value: 'stockout'},
    ];

    this.load = function(data) {
        this.keyword(data.keyword);
        this.actions($.map(data.actions, function(e) {
            return new ActionModel(e);
        }));
        this.loc_types($.map(data.loc_types, function(e) {
            return new LocationTypeModel(e);
        }));
        this.requisition_config(new RequisitionConfigModel(data.requisition_config));
        this.openlmis_config(new OpenLMISConfigModel(data.openlmis_config));
    };

    var settings = this;

    this.remove_action = function(action) {
        settings.actions.remove(action);
    };

    this.new_action = function() {
        settings.actions.push(new ActionModel({}));
    };

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
        this.keyword_error(null);
        this.loc_types_error(null);

        var that = this;
        var valid = true;

        if (!this.keyword()) {
            this.keyword_error('required');
            valid = false;
        }
        if (!this.validate_sms(this, 'keyword', 'command', 'stock_report')) {
            valid = false;
        }

        $.each(this.actions(), function(i, e) {
                if (!e.validate(that)) {
                    valid = false;
                }
            });
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

    this.all_sms_codes = function() {
        keywords = [];

        $.each(other_sms_codes, function(k, v) {
                keywords.push({keyword: k, type: v[0], name: 'product "' + v[1] + '"', id: null});
            });

        keywords.push({keyword: this.keyword(), type: 'command', name: 'stock report', id: 'stock_report'});

        $.each(this.actions(), function(i, e) {
                keywords.push({keyword: e.keyword(), type: 'action', name: e.caption(), id: i});
            });

        return keywords;
    };

    this.sms_code_uniqueness = function(keyword, type, id) {
        var conflict = null;
        $.each(this.all_sms_codes(), function(i, e) {
                if (keyword == e.keyword && !(type == e.type && id == e.id)) {
                    conflict = e;
                    return false;
                }
            });
        return conflict;
    };

    this.validate_sms = function(model, attr, type, id) {
        var conflict = this.sms_code_uniqueness(model[attr](), type, id);
        if (conflict) {
            model[attr + '_error']('conficts with ' + conflict.name);
            return false;
        }
        return true;
    };

    this.to_json = function() {
        return {
            keyword: this.keyword(),
            actions: $.map(this.actions(), function(e) { return e.to_json(); }),
            loc_types: $.map(this.loc_types(), function(e) { return e.to_json(); }),
            requisition_config: this.requisition_config().to_json(),
            openlmis_config: this.openlmis_config().to_json()
        };
    };
}

function ActionModel(data) {
    this.keyword = ko.observable(data.keyword);
    this.caption = ko.observable(data.caption);
    this.type = ko.observable(data.type);
    this.name = data.name;

    this.keyword_error = ko.observable();
    this.caption_error = ko.observable();

    this.validate = function(root) {
        this.keyword_error(null);
        this.caption_error(null);

        valid = true;

        if (!this.keyword()) {
            this.keyword_error('required');
            valid = false;
        }
        if (!this.caption()) {
            this.caption_error('required');
            valid = false;
        }

        if (!root.validate_sms(this, 'keyword', 'action', root.actions().indexOf(this))) {
            valid = false;
        }

        return valid;
    };

    this.to_json = function() {
        return {
            keyword: this.keyword(),
            caption: this.caption(),
            type: this.type(),
            name: this.name
        };
    };
}

function LocationTypeModel(data, root) {
    this.name = ko.observable(data.name || '\u2014');
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
    this.administrative = ko.observable(data.administrative);

    this.name_error = ko.observable();
    this.allowed_parents_error = ko.observable();

    this.validate = function() {
        this.name_error(null);
        this.allowed_parents_error(null);

        valid = true;

        if (!this.name()) {
            this.name_error('required');
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
            allowed_parents: this.allowed_parents(),
            administrative: this.administrative()
        };
    };
}

function RequisitionConfigModel(data) {
    // TODO: sort out possibly removing this redundant declaration in js
    this.action_types = [
        {label: 'Request', value: 'request'},
        {label: 'Approval', value: 'approval'},
        {label: 'Pack', value: 'pack'},
        {label: 'Receipts (Requisition)', value: 'requisition-receipts'}
    ];

    this.enabled = ko.observable(data.enabled);
    this.actions = ko.observableArray($.map(data.actions, function(item) {
        return new ActionModel(item);
    }));

    var that = this;
    this.remove_action = function(action) {
        that.actions.remove(action);
    };

    this.new_action = function() {
        that.actions.push(new ActionModel({}));
    };

    this.to_json = function() {
        return {
            enabled: this.enabled(),
            actions: $.map(this.actions(), function(e) { return e.to_json(); })
        };
    };
}


function OpenLMISConfigModel(data) {
    this.enabled = ko.observable(data.enabled);
    this.url = ko.observable(data.url);
    this.username = ko.observable(data.username);
    this.password = ko.observable(data.password);
    this.using_requisitions = ko.observable(data.using_requisitions);

    this.to_json = function() {
        return {
            enabled: this.enabled(),
            url: this.url(),
            username: this.username(),
            password: this.password(),
            using_requisitions: this.using_requisitions()
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
