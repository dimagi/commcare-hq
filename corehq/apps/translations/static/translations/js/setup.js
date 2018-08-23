hqDefine('translations/js/setup', [
    'jquery',
    'select2-3.5.2-legacy/select2'
], function(
    $,
) {
    $(function() {
        $("#id_source_lang").select2();
        $("#id_target_lang").select2();
    });
});
