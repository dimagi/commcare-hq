/* globals Blazy */
$(function () {
    var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get;

    // Demo CTA test
    hqImport("analytix/js/hubspot").then(function () {
        var kissmetrics = hqImport('analytix/js/kissmetrix');
        kissmetrics.identifyTraits({'demo UI': (initial_page_data("demo_test") ? "on" : "off")});
        $("#test-cta-form-get-demo-button").click(function () {
            kissmetrics.track.event("Test Get Demo CTA clicked");
        });
        $("#cta-form-get-demo-button").click(function () {
            kissmetrics.track.event("Get Demo button clicked");
        });
        $(".hs_submit .hs-button").click(function () {
            kissmetrics.track.event("Demo request sent");
        });
    });

    // Link up with registration form ko model
    var reg = hqImport('registration/js/new_user.ko');
    reg.onModuleLoad = function () {
        $('.loading-form-step').fadeOut(500, function () {
            $('.step-1').fadeIn(500);
        });
    };
    reg.initRMI(hqImport('hqwebapp/js/initial_page_data').reverse('process_registration'));
    if (!initial_page_data('hide_password_feedback')) {
        reg.showPasswordFeedback();
    }
    var regForm = reg.formViewModel(
        initial_page_data('reg_form_defaults'),
        '#registration-form-container',
        ['step-1', 'step-2', 'final-step']
    );
    $('#registration-form-container').koApplyBindings(regForm);

    // Email validation feedback
    reg.setResetEmailFeedbackFn(function (isValidating) {
        var $email = $('#div_id_email');
        if (isValidating) {
            $email.removeClass('has-error has-success').addClass('has-warning');
            $email.find('.form-control-feedback').removeClass('fa-check fa-remove').addClass('fa-spinner fa-spin');
        } else {
            var inputClass = 'has-error',
                iconClass = 'fa-remove';
            if (regForm.emailDelayed.isValid() && regForm.email.isValid()) {
                inputClass = 'has-success';
                iconClass = 'fa-check';
            }
            $email.removeClass('has-warning').addClass(inputClass);
            $email.find('.form-control-feedback').removeClass('fa-spinner fa-spin').addClass(iconClass);
        }
    });

    // Handle phone number input
    var $number = $('#id_phone_number');
    $number.intlTelInput({
        separateDialCode: true,
        utilsScript: initial_page_data('number_utils_script'),
    });
    $number.keydown(function (e) {
        // prevents non-numeric numbers from being entered.
        // from http://stackoverflow.com/questions/995183/how-to-allow-only-numeric-0-9-in-html-inputbox-using-jquery
        // Allow: backspace, delete, tab, escape, enter and .
        if ($.inArray(e.keyCode, [46, 8, 9, 27, 13, 110, 190]) !== -1 ||
            // Allow: Ctrl+A, Command+A
            (e.keyCode === 65 && (e.ctrlKey === true || e.metaKey === true)) ||
            // Allow: home, end, left, right, down, up
            (e.keyCode >= 35 && e.keyCode <= 40)
        ) {
            // let it happen, don't do anything
            return;
        }

        // Ensure that it is a number and stop the keypress
        if ((e.shiftKey || (e.keyCode < 48 || e.keyCode > 57)) && (e.keyCode < 96 || e.keyCode > 105)) {
            e.preventDefault();
        }
    });
    reg.setGetPhoneNumberFn(function () {
        return $number.intlTelInput("getNumber");
    });
});
