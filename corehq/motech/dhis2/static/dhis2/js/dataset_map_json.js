hqDefine('dhis2/js/dataset_map_json', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'hqwebapp/js/base_ace',
], function (
    $,
    ko,
    initialPageData,
    alertUser,
    baseAce
) {

    var ViewModel = function (data) {
        var self = {};
        self.dataSetMap = ko.observable(JSON.stringify(data, null, 4));

        self.submit = function (form) {
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
        _.each($('.observablejsonwidget'), baseAce.initObservableJsonWidget);
    });
});
