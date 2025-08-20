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
    self.dataSetMap = ko.observable(JSON.stringify(data, null, 4));
    self.errorMessage = ko.observable('');
    self.isError = ko.computed(function () {
        return self.errorMessage() !== '';
    });

    self.initMapConfigTemplate = function (elements) {
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
            {'dataset_map': self.dataSetMap()},
            function (data) {
                alertUser.alert_user(data['success'], 'success', true);
            },
        ).fail(function () {
            var msg = gettext('Unable to save DataSet map');
            alertUser.alert_user(msg, 'danger');
        });
    };

    return self;
};

$(function () {
    var viewModel = ViewModel(initialPageData.get('dataset_map'));
    $('#dataset-map').koApplyBindings(viewModel);
});
