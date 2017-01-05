/*globals hqDefine, ko, $ */
hqDefine('commtrack/js/sms.js', function () {
    'use strict';
    function CommtrackSettingsViewModel(other_sms_codes) {
        this.keyword = ko.observable();
        this.actions = ko.observableArray();
        this.requisition_config = ko.observable();

        this.json_payload = ko.observable();

        this.keyword_error = ko.observable();

        // TODO: sort out possibly removing this redundant declaration in js
        this.action_types = [
            {label: 'Stock on hand', value: 'stockonhand'},
            {label: 'Receipts', value: 'receipts'},
            {label: 'Consumption', value: 'consumption'},
            {label: 'Stock out', value: 'stockout'},
        ];

        this.load = function (data) {
            this.keyword(data.keyword);
            this.actions($.map(data.actions, function (e) {
                return new ActionModel(e);
            }));
            this.requisition_config(new RequisitionConfigModel(data.requisition_config));
        };

        var settings = this;

        this.remove_action = function (action) {
            settings.actions.remove(action);
        };

        this.new_action = function () {
            settings.actions.push(new ActionModel({}));
        };

        this.validate = function () {
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

            $.each(this.actions(), function (i, e) {
                if (!e.validate(that)) {
                    valid = false;
                }
            });

            return valid;
        };

        this.presubmit = function () {
            if (!this.validate()) {
                return false;
            }

            var payload = this.to_json();
            this.json_payload(JSON.stringify(payload));
        };

        this.all_sms_codes = function () {
            var keywords = [];

            $.each(other_sms_codes, function (k, v) {
                keywords.push({keyword: k, type: v[0], name: 'product "' + v[1] + '"', id: null});
            });

            keywords.push({keyword: this.keyword(), type: 'command', name: 'stock report', id: 'stock_report'});

            $.each(this.actions(), function (i, e) {
                keywords.push({keyword: e.keyword(), type: 'action', name: e.caption(), id: i});
            });

            return keywords;
        };

        this.sms_code_uniqueness = function (keyword, type, id) {
            var conflict = null;
            $.each(this.all_sms_codes(), function (i, e) {
                if (keyword === e.keyword && !(type === e.type && id === e.id)) {
                    conflict = e;
                    return false;
                }
            });
            return conflict;
        };

        this.validate_sms = function (model, attr, type, id) {
            var conflict = this.sms_code_uniqueness(model[attr](), type, id);
            if (conflict) {
                model[attr + '_error']('conficts with ' + conflict.name);
                return false;
            }
            return true;
        };

        this.to_json = function () {
            return {
                keyword: this.keyword(),
                actions: $.map(this.actions(), function (e) { return e.to_json(); }),
                requisition_config: this.requisition_config().to_json(),
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

        this.validate = function (root) {
            this.keyword_error(null);
            this.caption_error(null);

            var valid = true;

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

        this.to_json = function () {
            return {
                keyword: this.keyword(),
                caption: this.caption(),
                type: this.type(),
                name: this.name
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
        this.actions = ko.observableArray($.map(data.actions, function (item) {
            return new ActionModel(item);
        }));

        var that = this;
        this.remove_action = function (action) {
            that.actions.remove(action);
        };

        this.new_action = function () {
            that.actions.push(new ActionModel({}));
        };

        this.to_json = function () {
            return {
                enabled: this.enabled(),
                actions: $.map(this.actions(), function (e) { return e.to_json(); })
            };
        };
    }
    return {
        initCommtrackSettingsView: function ($element, settings, other_sms_codes) {
            var model = new CommtrackSettingsViewModel(other_sms_codes);
            $element.submit(function () {
                return model.presubmit();
            });

            model.load(settings);
            $element.koApplyBindings(model);
        }
    };
});
