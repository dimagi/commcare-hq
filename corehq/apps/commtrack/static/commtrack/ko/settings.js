
$(function() {
        
        var model = new CommtrackSettingsViewModel();
        $('#settings').submit(function() {
                return model.presubmit();
            });

        ko.applyBindings(model);
        model.load(settings);
        
    });

function CommtrackSettingsViewModel() {
    this.keyword = ko.observable();
    this.actions = ko.observableArray();
    this.json_payload = ko.observable();

    this.keyword_error = ko.observable();

    this.action_types = [
        {label: 'Stock on hand', value: 'stockonhand'},
        {label: 'Receipts', value: 'receipts'},
        {label: 'Consumption', value: 'consumption'},
        {label: 'Stock out', value: 'stockout'},
        {label: '# days stocked-out for', value: 'stockedoutfor'},
    ];

    this.load = function(data) {
        this.keyword(data.keyword);
        this.actions($.map(data.actions, function(e) {
                    return new ActionModel(e);
                }));
    }

    var settings = this;

    this.remove_action = function(action) {
        settings.actions.remove(action);
    }

    this.new_action = function() {
        settings.actions.push(new ActionModel({}));
    }

    this.validate = function() {
        this.keyword_error(null);

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

        return valid;
    }

    this.presubmit = function() {
        if (!this.validate()) {
            return false;
        }
        
        payload = ko.toJS(this);
        delete payload.action_types;
        delete payload.json_payload;

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
    }

    this.sms_code_uniqueness = function(keyword, type, id) {
        var conflict = null;
        $.each(this.all_sms_codes(), function(i, e) {
                if (keyword == e.keyword && !(type == e.type && id == e.id)) {
                    conflict = e;
                    return false;
                }
            });
        return conflict;
    }

    this.validate_sms = function(model, attr, type, id) {
        var conflict = this.sms_code_uniqueness(model[attr](), type, id);
        if (conflict) {
            model[attr + '_error']('conficts with ' + conflict.name);
            return false;
        }
        return true;
    }
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
    }
}

