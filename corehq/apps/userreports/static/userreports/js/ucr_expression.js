hqDefine("userreports/js/ucr_expression", [
    'moment',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/base_ace',
    'hqwebapp/js/bootstrap3/alert_user',
], function (
    moment,
    ko,
    _,
    initialPageData,
    baseAce,
    alertUser
) {
    let EditModel = function (data) {
        const mapping = {
            'copy': ["domain", "definition_raw"],
            'observe': ["name", "description", "expression_type"],
        };

        let self = ko.mapping.fromJS(data, mapping);

        self.definition = ko.observable(JSON.stringify(self.definition_raw, null, 2));

        self.getDefinitionJSON = function () {
            try {
                return JSON.parse(self.definition());
            } catch (err) {
                return null;
            }
        };

        self.hasParseError = ko.computed(function () {
            return self.getDefinitionJSON() === null;
        }, self);

        self.formatJson = function () {
            let expr = self.getDefinitionJSON();
            if (expr !== null) {
                self.editor.getSession().setValue(JSON.stringify(expr, null, 2));
            }
        };

        self.saveExpression = function (form) {
            $(form).ajaxSubmit({
                dataType: 'json',
                success: function (response) {
                    alertUser.alert_user(gettext("Expression saved"), 'success');
                    if (response.warning) {
                        alertUser.alert_user(response.warning, 'warning');
                    }
                },
                error: function (response) {
                    if (response.responseJSON && response.responseJSON.errors) {
                        _.each(response.responseJSON.errors, function (error) {
                            alertUser.alert_user(error, 'danger');
                        });
                    }
                },
            });
            return false;
        };

        return self;
    };

    $(function () {
        let viewModel = EditModel(
            initialPageData.get("expression")
        );
        $("#edit-expression").koApplyBindings(viewModel);
        viewModel.editor = baseAce.initObservableJsonWidget($('.observablejsonwidget')[0]);
    });
});
