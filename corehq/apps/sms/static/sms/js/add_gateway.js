hqDefine('sms/js/add_gateway', function() {
        var gatewayFormHandler = new AddGatewayFormHandler({
            share_backend: {{ form.give_other_domains_access.value|BOOL }},
            use_load_balancing: {{ use_load_balancing|BOOL }},
            phone_numbers: {{ form.phone_numbers.value|default:'[]'|safe }},
            phone_number_required_text: "{% trans 'You must have at least one phone number.' %}"
        });
        $('#add-gateway-form').koApplyBindings(gatewayFormHandler);
        gatewayFormHandler.init();
});
