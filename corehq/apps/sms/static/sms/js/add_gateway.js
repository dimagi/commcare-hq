hqDefine('sms/js/add_gateway', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
        var gatewayFormHandler = new AddGatewayFormHandler({
            share_backend: initialPageData.get('form').give_other_domains_access.value,
            use_load_balancing: initialPageData.get('use_load_balancing'),
            phone_numbers: initialPageData.get('form').phone_numbers.value || '[]',
            phone_number_required_text: gettext('You must have at least one phone number.'),
        });
        $('#add-gateway-form').koApplyBindings(gatewayFormHandler);
        gatewayFormHandler.init();
});
