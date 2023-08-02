hqDefine("hqwebapp/js/bootstrap5/500",[
    'jquery',
    'bootstrap',
], function ($) {
    $(function () {
        $('#sad-danny').popover({
            title: gettext("This is Danny, one of our best developers."),
            content: gettext("Danny is pretty sad that you had to encounter this issue. He's making sure it gets fixed as soon as possible."),
        });
        $('#refresh').click(function () {
            window.location.reload(true);
        });
    });
});
