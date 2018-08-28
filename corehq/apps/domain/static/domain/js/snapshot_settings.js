hqDefine("domain/js/snapshot_settings", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'analytix/js/google',
], function(
    $,
    _,
    initialPageData,
    googleAnalytics
) {
    function viewOnExchange() {
        var versionName = $(this).data('version');
        googleAnalytics.track.click($('#view-on-exchange'), 'Exchange', 'View on exchange', versionName);
    }
    function projectPublishEventTrack(){
        var versionName = $(this).data('version');
        googleAnalytics.track.event('Exchange', 'Publish Most Recent', versionName);
    }

    $(function() {
        $("#contentDistributionAgreement").on("show.bs.modal", function() {
            $(this).find(".modal-body").load(initialPageData.reverse('cda_basic'));
        });

        $('[data-target="#contentDistributionAgreement"]').click(function() {
            var new_action = $(this).attr('data-action');
            $('#cda-agree').attr('action', new_action);
        });

        $('#toggle-snapshots').click(function() {
            if ($(this).text() === 'Show previous versions') {
                $('#snapshots').show(500);
                $(this).text(gettext('Hide previous versions'));
            }
            else {
                $('#snapshots').hide(500);
                $(this).text(gettext('Show previous versions'));
            }
        });

        _.each(initialPageData.get('snapshots'), function(snapshot) {
            $('#publish_' + snapshot.name).click(function() {
                googleAnalytics.track.event('Exchange', 'Publish Previous Version', snapshot.name);
            });
            $('#view_' + snapshot.name).click(function() {
                googleAnalytics.track.click($('#view_' + snapshot.name), 'Exchange', 'View', snapshot.name);
            });
        });
    });


    $('#view-on-exchange').on('click',viewOnExchange);
    $('#project-publish').on('click',projectPublishEventTrack);

});
