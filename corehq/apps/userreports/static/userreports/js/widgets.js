hqDefine("userreports/js/widgets", [
    'jquery',
], function ($) {
    $(function () {
        $('[data-toggle="popover"]').popover();
        $(".submit-dropdown-form").click(function (e) {
            e.preventDefault();
            var $form = $("#dropdown-form");
            $form.attr("action", $(this).data("action"));
            $form.submit();
        });
    });
});
