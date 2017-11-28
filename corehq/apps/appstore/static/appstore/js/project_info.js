/* globals hqDefine */
hqDefine('appstore/js/project_info', function () {
    function update_import_into_button() {
        var project = $('#project_select option:selected').text();
        $("#import-into-button").text("Import into " + project);
    }

    $(function(){
        update_import_into_button();
    
        $("#import-app-button").click(function() {
            $('#import-app').removeClass('hide');
        });
    
        $('#project_select').change(update_import_into_button);
    
        $('[data-target="#licenseAgreement"]').click(function() {
            var new_form = $(this).attr('data-form');
            $('#agree-button').attr('data-form', new_form);
        });
        $('#agree-button').click(function() {
            $('#agree-button').unbind()
                              .addClass('disabled');
            $('#download-new-project').removeProp('data-toggle');
            $('#download-new-project').removeProp('href');
            $('#import-into-button').removeProp('data-toggle');
            $('#import-into-button').removeProp('href');
            var form = $("#" + $(this).attr('data-form'));
            form.submit();
        });
    
        // Analytics
        var project = hqImport('hqwebapp/js/initial_page_data').get('project');
        $('#download-new-project').click(function() {
            hqImport('analytix/js/google').track.event('Exchange', 'Download As New Project', project);
        });
    
        $('#import-app-button').click(function() {
            hqImport('analytix/js/google').track.event('Exchange', 'Download to Existing Project', project);
        });
    });
});
