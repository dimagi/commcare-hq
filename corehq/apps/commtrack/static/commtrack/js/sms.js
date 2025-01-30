hqDefine('commtrack/js/sms', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'commcarehq',
], function (
    $,
    ko,
    initialPageData
) {
    'use strict';
    function commtrackSettingsViewModel(otherSmsCodes) {
        var self = {};
        self.actions = ko.observableArray();

        self.json_payload = ko.observable();

        self.keyword_error = ko.observable();

        // TODO: sort out possibly removing this redundant declaration in js
        self.action_types = [
            {label: 'Stock on hand', value: 'stockonhand'},
            {label: 'Receipts', value: 'receipts'},
            {label: 'Consumption', value: 'consumption'},
            {label: 'Stock out', value: 'stockout'},
        ];

        self.load = function (data) {
            self.actions($.map(data.actions, function (e) {
                return actionModel(e);
            }));
        };

        self.remove_action = function (action) {
            self.actions.remove(action);
        };

        self.new_action = function () {
            self.actions.push(actionModel({}));
        };

        self.validate = function () {
            self.keyword_error(null);

            var that = self;
            var valid = true;

            $.each(self.actions(), function (i, e) {
                if (!e.validate(that)) {
                    valid = false;
                }
            });

            return valid;
        };

        self.presubmit = function () {
            if (!self.validate()) {
                return false;
            }

            var payload = self.to_json();
            self.json_payload(JSON.stringify(payload));
        };

        self.all_sms_codes = function () {
            var keywords = [];

            $.each(otherSmsCodes, function (k, v) {
                keywords.push({keyword: k, type: v[0], name: 'product "' + v[1] + '"', id: null});
            });

            $.each(self.actions(), function (i, e) {
                keywords.push({keyword: e.keyword(), type: 'action', name: e.caption(), id: i});
            });

            return keywords;
        };

        self.sms_code_uniqueness = function (keyword, type, id) {
            var conflict = null;
            $.each(self.all_sms_codes(), function (i, e) {
                if (keyword === e.keyword && !(type === e.type && id === e.id)) {
                    conflict = e;
                    return false;
                }
            });
            return conflict;
        };

        self.validate_sms = function (model, attr, type, id) {
            var conflict = self.sms_code_uniqueness(model[attr](), type, id);
            if (conflict) {
                model[attr + 'Error']('conficts with ' + conflict.name);
                return false;
            }
            return true;
        };

        self.to_json = function () {
            return {
                actions: $.map(self.actions(), function (e) { return e.to_json(); }),
            };
        };

        return self;
    }

    function actionModel(data) {
        var self = {};
        self.keyword = ko.observable(data.keyword);
        self.caption = ko.observable(data.caption);
        self.type = ko.observable(data.type);
        self.name = data.name;

        self.keywordError = ko.observable();
        self.captionError = ko.observable();

        self.validate = function (root) {
            self.keywordError(null);
            self.captionError(null);

            var valid = true;

            if (!self.keyword()) {
                self.keywordError(gettext('SMS keyword is required.'));
                valid = false;
            }
            if (!self.caption()) {
                self.captionError(gettext('Name is required.'));
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

    function initCommtrackSettingsView($element, settings, otherSmsCodes) {
        var model = commtrackSettingsViewModel(otherSmsCodes);
        $element.submit(function () {
            return model.presubmit();
        });

        model.load(settings);
        $element.koApplyBindings(model);
    }

    $(function () {
        var settings = initialPageData.get('settings');
        var otherSmsCodes = initialPageData.get('other_sms_codes');
        initCommtrackSettingsView($('#settings'), settings, otherSmsCodes);
    });
});
