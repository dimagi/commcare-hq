hqDefine("app_manager/js/form_view.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    $(function (){
        if (COMMCAREHQ.toggleEnabled('CUSTOM_INSTANCES')) {
            var customInstances = hqImport('app_manager/js/custom_intances.js').wrap({
                customInstances: initial_page_data('custom_instances'),
            });
            $('#custom-instances').koApplyBindings(customInstances);
        }

        var setupValidation = hqImport('app_manager/js/app_manager.js').setupValidation;
        setupValidation(hqImport("hqwebapp/js/urllib.js").reverse("validate_form_for_build"));

        // Data dictionary descriptions for case properties
        $('.property-description').popover();

        // Advanced > XForm > Upload
        (function(){
            $("#xform_file_input").change(function(){
                if ($(this).val()) {
                    $("#xform_file_submit").show();
                } else {
                    $("#xform_file_submit").hide();
                }
            }).trigger('change');
        }());

        // Advanced > XForm > View
        $("#xform-source-opener").click(function(evt){
            if (evt.shiftKey) {
                // Shift+click: edit form source
                $(".source-readonly").hide();
                $(".source-edit").show();
                $.get($(this).data('href'), function (data) {
                    $("#xform-source-edit").text(data).blur();
                }, 'json');
            } else {
                // Plain click: view form source
                $(".source-edit").hide();
                $(".source-readonly").show();
                $("#xform-source").text("Loading...");
                $.get($(this).data('href'), function (data) {
                    var brush = new SyntaxHighlighter.brushes.Xml();
                    brush.init({ toolbar: false });
                    // brush.getDiv seems to escape inconsistently, so I'm helping it out
                    data = data.replace(/&/g, '&amp;');
                    $("#xform-source").html(brush.getDiv(data));
                }, 'json');
            }
            $(".xml-source").modal();
        });
    });
});
