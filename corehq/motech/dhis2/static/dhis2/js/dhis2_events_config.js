import "commcarehq";
import $ from "jquery";
import _ from "underscore";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import alertUser from "hqwebapp/js/bootstrap5/alert_user";
import baseAce from "hqwebapp/js/base_ace";
import jsonParse from "dhis2/js/json_syntax_parse";

var ViewModel = function (data) {
    var self = {};
    data = data ? data : [];
    self.formConfigs = ko.observable(JSON.stringify(data, null, 2));
    self.errorMessage = ko.observable('');
    self.isError = ko.computed(function () {
        return self.errorMessage() !== '';
    });

    self.initFormConfigTemplate = function (elements) {
        _.each(elements, function (element) {
            _.each($(element).find('.jsonwidget'), baseAce.initObservableJsonWidget);
        });
    };

    self.submit = function (form) {
        var editors = baseAce.getEditors();
        var value = editors[0].getValue();
        try {
            jsonParse.parseJson(value, null, 30);
        } catch (error) {
            self.errorMessage(error);
            return self;
        }
        self.errorMessage(''); // clears error message from page before submitting
        $.post(
            form.action,
            {'form_configs': self.formConfigs()},
            function (data) {
                alertUser.alert_user(data['success'], 'success', true);
            },
        ).fail(
            function (data) {
                var errors = '<ul><li>' + data.responseJSON['errors'].join('</li><li>') + '</li></ul>';
                alertUser.alert_user(gettext('Unable to save form configs') + errors, 'danger');
            },
        );
    };

    return self;
};

$(function () {
    var viewModel = ViewModel(initialPageData.get('form_configs'));
    $('#dhis2-form-config').koApplyBindings(viewModel);
});
