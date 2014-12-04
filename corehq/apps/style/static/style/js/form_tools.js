$.fn.activateSubmitOnlyOnChange = function () {
    var $form = $(this);
    if ($form.prop('tagName') === 'FORM') {
        var changeSubmitState = function (is_disabled) {
            return function () {
                $form.find('button[type="submit"]').prop('disabled', is_disabled);
            };
        };
        changeSubmitState(true)();
        $form
            .on('change', changeSubmitState(false))
            .on('input', changeSubmitState(false));
    } else {
        console.warn("activateSubmitOnlyOnChange should only be applied to forms.");
    }
};
