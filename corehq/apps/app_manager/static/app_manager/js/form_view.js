hqDefine("app_manager/js/form_view.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    $(function (){
        if (COMMCAREHQ.toggleEnabled(CUSTOM_INSTANCES)) {
            var customInstances = hqImport('app_manager/js/custom_intances.js').wrap({
                customInstances: initial_page_data('custom_instances');
            });
            $('#custom-instances').koApplyBindings(customInstances);
        }

        var setupValidation = hqImport('app_manager/js/app_manager.js').setupValidation;
        setupValidation(hqImport("hqwebapp/js/urllib.js").reverse("validate_form_for_build"));

        // Data dictionary descriptions for case properties
        $('.property-description').popover();
    });
});
