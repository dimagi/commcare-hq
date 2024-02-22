/* jQuery extension for password reset widget. Only used by app settings. */

$.fn.password_setter = function () {
    var that = this,
        randID = Math.floor(Math.random() * 1000),
        password1ID = 'password-' + randID + '-1',
        password2ID = 'password-' + randID + '-2',
        $popupLink = $('<a/>').text(gettext("Reset")).attr({
            href: '#password-setter',
            'data-toggle': 'modal',
        }),
        $modal = $("#password-setter"),
        $passwordRow = $modal.find(".password"),
        $passwordInput = $passwordRow.find("input"),
        $repeatRow = $modal.find(".repeat-password"),
        $repeatInput = $repeatRow.find("input"),
        $errorMismatch = $modal.find(".password-mismatch"),
        $errorEmpty = $modal.find(".password-empty");

    that.hide();
    that.after($popupLink);
    $popupLink.click(function () {
        $passwordRow.find("input").focus();
    });

    $passwordRow.find("label").attr("for", password1ID);
    $passwordInput.attr("id", password1ID);
    $repeatRow.find("label").attr("for", password2ID);
    $repeatInput.find("input").attr("id", password2ID);

    $modal.find("button.save").click(function () {
        $errorMismatch.addClass("hide");
        $errorEmpty.addClass("hide");
        if ($passwordInput.val() !== $repeatInput.val()) {
            $errorMismatch.removeClass("hide");
        } else if (!$passwordInput.val()) {
            $errorEmpty.removeClass("hide");
        } else {
            $modal.modal('hide');
            that.val($passwordInput.val()).trigger('textchange');
        }
    });
};
