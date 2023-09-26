hqDefine('dhis2/js/dhis2_entity_config', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/alert_user',
    'hqwebapp/js/base_ace',
    'dhis2/js/json_syntax_parse',
], function (
    $,
    _,
    ko,
    initialPageData,
    alertUser,
    baseAce,
    jsonParse
) {
    var caseConfig = function (data) {
        var self = {};
        self.oCaseConfig = ko.observable(JSON.stringify(data, null, 2));
        self.toJSON = function () {
            return JSON.parse(self.oCaseConfig());
        };
        return self;
    };

    var dhis2EntityConfig = function (caseConfigs) {
        var self = {};
        self.oCaseConfigs = ko.observableArray();
        self.errorMessage = ko.observable('');
        self.isError = ko.computed(function () {
            return self.errorMessage() !== '';
        });

        self.init = function () {
            if (caseConfigs.length > 0) {
                self.oCaseConfigs(_.map(caseConfigs, caseConfig));
            } else {
                self.addCaseConfig();
            }
        };

        self.addCaseConfig = function () {
            var conf = caseConfig({});
            self.oCaseConfigs.push(conf);
        };

        self.removeCaseConfig = function (conf) {
            self.oCaseConfigs.remove(conf);
        };

        self.initCaseConfigTemplate = function (elements) {
            _.each(elements, function (element) {
                _.each($(element).find('.jsonwidget'), baseAce.initObservableJsonWidget);
            });
        };

        self.submit = function (form) {
            var editors = baseAce.getEditors();
            var errors = [];
            for (let i = 0; i < editors.length; i++) {
                var value = editors[i].getValue();
                try {
                    if (editors.length > 1) {
                        jsonParse.parseJson(value, null, 30, i);
                    } else {
                        jsonParse.parseJson(value, null, 30);
                    }
                } catch (error) {
                    errors.push(String(error));
                }
            }
            if (errors.length > 0) {
                self.errorMessage(errors.join('\n----------------------\n'));
                return self;
            }
            self.errorMessage(''); // clears error message from page before submitting
            $.post(
                form.action,
                {'case_configs': JSON.stringify(self.oCaseConfigs())},
                function (data) {
                    alertUser.alert_user(data['success'], 'success', true);
                }
            ).fail(
                function (data) {
                    var errors = '<ul><li>' + data.responseJSON['errors'].join('</li><li>') + '</li></ul>';
                    alertUser.alert_user(gettext('Unable to save case configs') + errors, 'danger');
                }
            );
        };

        return self;
    };

    $(function () {
        var viewModel = dhis2EntityConfig(
            initialPageData.get('case_configs')
        );
        viewModel.init();
        $('#dhis2-entity-config').koApplyBindings(viewModel);
    });
});
