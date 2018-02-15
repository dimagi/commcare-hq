hqDefine('sms/js/add_gateway', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data'),
        AddGatewayFormHandler = hqImport('sms/js/add_gateway_form_handler').AddGatewayFormHandler;

    $(function () {
        var gatewayFormHandler = new AddGatewayFormHandler({
            share_backend: initialPageData.get('give_other_domains_access'),
            use_load_balancing: initialPageData.get('use_load_balancing'),
            phone_numbers: initialPageData.get('phone_numbers'),
            phone_number_required_text: gettext('You must have at least one phone number.'),
        });
        $('#add-gateway-form').koApplyBindings(gatewayFormHandler);
        gatewayFormHandler.init();
    });
});
