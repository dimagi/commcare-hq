hqDefine("reports/js/export_action_download", function() {
    $('.export-action-download').click(function() {
        var $modalBody = $("#export-download-status .modal-body");
        $modalBody.text("Fetching...");
        console.log($(this).data("formname"));
        $("#export-download-status .modal-header h3 span").text($(this).data("formname"));
        console.log("Going to...");
        console.log($(this).data('dlocation'));
        $.getJSON($(this).data('dlocation'), function(d) {
            console.log("supposedly things should have worked");
            console.log(d.download_url);
            $modalBody.empty().load(d.download_url);
        });
    });
});
