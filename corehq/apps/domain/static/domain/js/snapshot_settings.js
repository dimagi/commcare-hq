/* globals hqDefine */
hqDefine("domain/js/snapshot_settings", function() {
    function view_on_exchange(version_name) {
        hqImport('analytics/js/google').track.click($('#view-on-exchange'), 'Exchange', 'View on exchange', version_name);
        return false;
    }
    
    $(function() {
        $("#contentDistributionAgreement").on("show.bs.modal", function() {
            $(this).find(".modal-body").load(hqImport('hqwebapp/js/initial_page_data').reverse('cda_basic'));
        });
    
        $('[data-target="#contentDistributionAgreement"]').click(function() {
            var new_action = $(this).attr('data-action');
            $('#cda-agree').attr('action', new_action);
        });
    
        $('#toggle-snapshots').click(function() {
            if ($(this).text() === 'Show previous versions') {
                $('#snapshots').show(500);
                $(this).text(django.gettext('Hide previous versions'));
            }
            else {
                $('#snapshots').hide(500);
                $(this).text(django.gettext('Show previous versions'));
            }
        });
    
        _.each(hqImport('hqwebapp/js/initial_page_data').get('snapshots'), function(snapshot) {
            $('#publish_' + snapshot.name).click(function() {
                ga_track_event('Exchange', 'Publish Previous Version', snapshot.name);
            });
            $('#view_' + snapshot.name).click(function() {
                hqImport('analytics/js/google').track.click($('#view_' + snapshot.name), 'Exchange', 'View', snapshot.name);
            });
        });
    });
});
