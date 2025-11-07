import "commcarehq";
import $ from "jquery";
import newUser from "registration/js/new_user.ko";
import initialPageData from "hqwebapp/js/initial_page_data";
import "registration/js/bootstrap5/login";

newUser.setOnModuleLoad(function () {
    $('.loading-form-step').fadeOut(500, function () {
        $('.user-step').fadeIn(500);
    });
});
newUser.initRMI(initialPageData.reverse('process_registration'));
if (!initialPageData.get('hide_password_feedback')) {
    newUser.showPasswordFeedback();
}

var regForm = newUser.formViewModel(
    initialPageData.get('reg_form_defaults'),
    '#registration-form-container',
    ['user-step', 'project-step', 'final-step'],
);
$('#registration-form-container').koApplyBindings(regForm);

// Email validation feedback
newUser.setResetEmailFeedbackFn(function () {
    // noop, bootstrap 5 styles handle this automatically
});
newUser.setPhoneNumberInput('#id_phone_number');
