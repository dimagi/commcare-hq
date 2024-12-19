hqDefine('sms/js/add_gateway',[
    "jquery",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "sms/js/add_gateway_form_handler",
    "commcarehq",
], function ($, _, initialPageData,addGatewayFormHandler) {
    function addParam($widget, count, nm, val) {
        $widget.append('<tr> \
                <td><input type="text" class="form-control" name="additional_params.' + count + '.name" value="' + nm + '" /></td> \
                <td><input type="text" class="form-control" name="additional_params.' + count + '.value" value="' + val + '" /></td> \
                <td><span id="id_remove_record_' + count + '" class="btn btn-danger"><i class="fa fa-remove"></i> ' + gettext('Remove') + '</span></td> \
            </tr>');
        $("#id_remove_record_" + count).click(function () {
            $(this).parent().parent().remove();
        });
        count++;
        return count;
    }

    $(function () {
        var gatewayFormHandler = addGatewayFormHandler.addGatewayFormHandler({
            share_backend: initialPageData.get('give_other_domains_access'),
            use_load_balancing: initialPageData.get('use_load_balancing'),
            phone_numbers: initialPageData.get('phone_numbers'),
            phone_number_required_text: gettext('You must have at least one phone number.'),
        });
        $('#add-gateway-form').koApplyBindings(gatewayFormHandler);
        gatewayFormHandler.init();

        $(".record-list-widget").each(function () {
            var count = 0,
                $widget = $(this),
                name = $widget.data("name"),
                value = $widget.data("value");

            _.each(value, function (pair) {
                count = addParam($widget, count, pair.name, pair.value);
            });

            $("#id_add_" + name).click(function () {
                count = addParam($widget, count, "", "");
            });
        });
    });
});
