'use strict';
hqDefine("hqwebapp/js/captcha", [
    'jquery',
],function (
    $
) {
    $(function () {
        // http://stackoverflow.com/a/20371801
        $('img.captcha').after(
            $('<span> <button class="captcha-refresh">' +
              '<i class="fa fa-refresh icon icon-refresh"></i></button></span>')
        );
        $('.captcha-refresh').click(function () {
            var $form = $(this).parent().closest('form');
            $.getJSON("/captcha/refresh/", {}, function (json) {
                $form.find('input[name$="captcha_0"]').val(json.key);
                $form.find('img.captcha').attr('src', json.image_url);
            });
            return false;
        });
    });
});
