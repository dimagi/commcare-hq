hqDefine('userreports/js/data_source_from_app', [
    'jquery',
    'userreports/js/data_source_select_model',
    'commcarehq',
], function (
    $,
    dataModel,
) {
    $(function () {
        $("#data-source-config").koApplyBindings(dataModel);
    });
});
