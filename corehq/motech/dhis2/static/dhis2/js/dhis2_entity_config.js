hqDefine('dhis2/js/dhis2_entity_config', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'hqwebapp/js/base_ace',
], function (
    $,
    _,
    ko,
    initialPageData,
    alertUser,
    baseAce
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
        self.isError = ko.computed(function() {
            return self.errorMessage() === '' ? false : true
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
            console.log("submitting")
            var editors = baseAce.returnEditors();
            console.log(editors)
            for (let i = 0; i < editors.length; i++) {
                var annotations = editors[i].getSession().getAnnotations()
                console.log(annotations)
                if (annotations.length > 0) {
                    for (let i = 0; i < annotations.length; i++) {
                        var row = annotations[0]['row']
                            error = annotations[0]['text'];
                        var text = `Syntax error on row ${row}: `;
                        self.errorMessage(text + error);
                    };
                    return self;
                };
            };
            try {
                JSON.stringify(self.oCaseConfigs());
            } catch (error) {
                console.log("Error!!!")
                console.log(error);
                return self;
            }
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
