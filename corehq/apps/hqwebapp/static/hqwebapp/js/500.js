hqDefine("hqwebapp/js/500",[
    'jquery',
    'es6!hqwebapp/js/bootstrap5_loader',
], function ($, bootstrap) {
    $(function () {
        new bootstrap.Popover('#sad-danny', {
            title: gettext("This is Danny, one of our best developers."),
            content: gettext("Danny is pretty sad that you had to encounter this issue. He's making sure it gets fixed as soon as possible.")
        });
        $('#refresh').click(function () {
            window.location.reload(true);
        });
    });
});
