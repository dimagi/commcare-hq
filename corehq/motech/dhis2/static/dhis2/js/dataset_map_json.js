hqDefine('dhis2/js/dataset_map_json', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
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
    var ViewModel = function (data) {
        var self = {};
        self.dataSetMap = ko.observable(JSON.stringify(data, null, 4));
        self.errorMessage = ko.observable('');
        self.isError = ko.computed(function() {
            return self.errorMessage() === '' ? false : true
        });

        self.initMapConfigTemplate = function (elements) {
            _.each(elements, function (element) {
                _.each($(element).find('.jsonwidget'), baseAce.initObservableJsonWidget);
            });
        };

        self.submit = function (form) {
            var editors = baseAce.returnEditors();
            var value = editors[0].getValue();
            try {
              var result = jsonParse.parseJson(value, null, 30)
            } catch (error) {
              self.errorMessage(error)
              return self;
            }
            self.errorMessage('')
            $.post(
                form.action,
                {'dataset_map': self.dataSetMap()},
                function (data) {
                    alertUser.alert_user(data['success'], 'success', true);
                }
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
});
