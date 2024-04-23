'use strict';
// To stack icon-uploader modal on top of key-value-mapping modal
// Hide modal into the stack
$(document).on('show.bs.modal', '#hqimage', function () {
    var $km = $(".modal.in");
    $km.addClass("stacked-modal");
    $km.hide();
});
// Pop out hidden stack onto top
$(document).on('hide.bs.modal', '#hqimage', function () {
    var $km = $(".stacked-modal");
    $km.removeClass("stacked-modal");
    $km.show();
});
