hqDefine("domain/js/create_snapshot", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'analytix/js/google',
    'jquery-ui/ui/datepicker',
], function (
    $,
    _,
    initialPageData,
    googleAnalytics
) {
    $(function () {
        var ids = initialPageData.get('app_ids').concat(initialPageData.get('fixture_ids'));

        _.each(ids, function (id) {
            var publish = $('#id_' + id + '-publish');
            publish.change(function () {
                $(this).parent().parent().parent().next().slideToggle();
            });
            publish.parent().parent().parent().next().toggle(publish.is(':checked'));
            $('#id_' + id + '-deployment_date').datepicker({
                changeMonth: true,
                changeYear: true,
                showButtonPanel: true,
                dateFormat: 'yy-mm-dd',
                maxDate: '0',
                numberOfMonths: 2,
            });
        });

        $('#save-button').on('click', function () {
            $('#id_publish_on_submit').val('no');
            $('#snapshot-form').submit();
        });

        $('input:radio[name="publisher"]').change(function () {
            if ($(this).val() === 'user') {
                $('#author-input').show(250);
            } else {
                $('#author-input').hide(250);
            }
        });

        $('#publish-now-button').on('click', function () {
            googleAnalytics.track.event('Exchange', 'Publish Now', '?', "", {}, function () {
                $('#snapshot-form').submit();
            });
        });
    });
});
