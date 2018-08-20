/*globals hqDefine, ko, $ */
hqDefine('commtrack/js/sms', function () {
    'use strict';
    function CommtrackSettingsViewModel(other_sms_codes) {
        this.actions = ko.observableArray();

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
            this.actions($.map(data.actions, function (e) {
                return actionModel(e);
            }));
        };

        var settings = this;

        this.remove_action = function (action) {
            settings.actions.remove(action);
        };

        this.new_action = function () {
            settings.actions.push(actionModel({}));
        };

        this.validate = function () {
            this.keyword_error(null);

            var that = this;
            var valid = true;

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
                model[attr + 'Error']('conficts with ' + conflict.name);
                return false;
            }
            return true;
        };

        this.to_json = function () {
            return {
                actions: $.map(this.actions(), function (e) { return e.to_json(); }),
            };
        };
    }

    function actionModel(data) {
        let self = {};
        self.keyword = ko.observable(data.keyword);
        self.caption = ko.observable(data.caption);
        self.type = ko.observable(data.type);
        self.name = data.name;

        self.keywordError = ko.observable();
        self.captionError = ko.observable();

        self.validate = function (root) {
            self.keywordError(null);
            self.captionError(null);

            let valid = true;

            if (!self.keyword()) {
                self.keywordError('required');
                valid = false;
            }
            if (!self.caption()) {
                self.captionError('required');
                valid = false;
            }

            if (!root.validate_sms(self, 'keyword', 'action', root.actions().indexOf(self))) {
                valid = false;
            }

            return valid;
        };

        self.to_json = function () {
            return {
                keyword: self.keyword(),
                caption: self.caption(),
                type: self.type(),
                name: self.name,
            };
        };

        return self;
    }

    function initCommtrackSettingsView($element, settings, other_sms_codes) {
        var model = new CommtrackSettingsViewModel(other_sms_codes);
        $element.submit(function () {
            return model.presubmit();
        });

        model.load(settings);
        $element.koApplyBindings(model);
    }

    $(function () {
        var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get;
        var settings = initial_page_data('settings');
        var other_sms_codes = initial_page_data('other_sms_codes');
        initCommtrackSettingsView($('#settings'), settings, other_sms_codes);
    });
});
