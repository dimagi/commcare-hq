
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
        var valid = true;

        if (!this.keyword()) {
            this.keyword_error('required');
            valid = false;
        }

        $.each(this.actions(), function(i, e) {
                if (!e.validate()) {
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
}

function ActionModel(data) {
    this.keyword = ko.observable(data.keyword);
    this.caption = ko.observable(data.caption);
    this.type = ko.observable(data.type);
    this.name = data.name;

    this.keyword_error = ko.observable();
    this.caption_error = ko.observable();

    this.validate = function() {
        valid = true;

        if (!this.keyword()) {
            this.keyword_error('required');
            valid = false;
        }
        if (!this.caption()) {
            this.caption_error('required');
            valid = false;
        }

        return valid;
    }
}

