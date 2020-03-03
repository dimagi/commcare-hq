hqDefine('registration/js/register_new_user', [
    'jquery',
    'knockout',
    'underscore',
    'registration/js/new_user.ko',
    'hqwebapp/js/initial_page_data',
    'analytix/js/kissmetrix',
    'registration/js/login',
], function (
    $,
    ko,
    _,
    newUser,
    initialPageData,
    kissmetrics 
) {
    'use strict';

    $('#js-create-account').click(function (e) {
        e.preventDefault();
        $('#registration-choose-plan-container').hide();
        $('#registration-form-container').fadeIn();

        $('#back-to-start-btn').removeClass('hide');
    });

    $('#back-to-start-btn').click(function () {
        $('#registration-form-container').hide();
        $('#registration-choose-plan-container').fadeIn();
    });

    $('#book-to-call-btn').click(function(){
        $('#get-trial-cta-calendar-content').fadeIn();
        $('#choose-callback-options').addClass('hide');

        // Loading the Schedule visit form.    
        $.getScript('//cdn.scheduleonce.com/mergedjs/so.js')
            .done(function () {
                kissmetrics.track.event("Get Trial Workflow - Loaded Booking Options");
                setTimeout(function () {
                    // This is a bit of a hack, but the only way to detect if
                    // the Schedule Once Form was submitted on our side.
                    // The style attribute changes when the form is successfully
                    // submitted.
                    var lastKnownHeight = 0,
                        observer = new MutationObserver(function (mutations) {
                            mutations.forEach(function () {
                                var newHeight = $('#SOIDIV_CommCareTrial').height();
                                if (newHeight < lastKnownHeight) {
                                    var coreUrl = document.location.href.split('?')[0];
                                    kissmetrics.track.event("Get Trial Workflow - Trial Scheduled");
                                    $('#cta-form-get-trial ').off('hide.bs.modal');
                                    window.history.pushState({}, document.title, coreUrl);
                                }
                                lastKnownHeight = newHeight;

                            });
                        });
                    // target is the the iframe containing the schedule once form
                    var target = document.getElementById('SOIDIV_CommCareTrial');
                    observer.observe(target, { attributes: true, attributeFilter: ['style'] });
                }, 3000);
            });
                
    });

    $('#get-callback-btn').click(function(){
        $('#start-trial-modal-header').text("Got it! We’ll be in touch soon");
        $('#will-be-in-touch-content').fadeIn();
        $('#choose-callback-options').addClass('hide');
    });

    kissmetrics.whenReadyAlways(function () {

        $('#js-start-trial').click(function () {
            kissmetrics.track.event("Signup alt ux dec2018 - clicked start trial");
        });

        $('#js-get-tour').click(function () {
            kissmetrics.track.event("Signup alt ux dec2018 - clicked get a tour");
            kissmetrics.track.event("Demo Workflow - Get A Tour Button Clicked (new UX)");
        });

        $('#start-chat-cta-btn').click(function () {
            kissmetrics.track.event("Signup alt ux dec2018 - clicked start chat");
        });
    });

    newUser.setOnModuleLoad(function () {
        $('.loading-form-step').fadeOut(500, function () {
            $('.step-1').fadeIn(500);
        });
    });
    newUser.initRMI(initialPageData.reverse('process_registration'));
    if (!initialPageData.get('hide_password_feedback')) {
        newUser.showPasswordFeedback();
    }

    var regForm = newUser.formViewModel(
        initialPageData.get('reg_form_defaults'),
        '#registration-form-container',
        ['step-1', 'step-2', 'final-step']
    );
    $('#registration-form-container').koApplyBindings(regForm);

    // Email validation feedback
    newUser.setResetEmailFeedbackFn(function (isValidating) {
        var $email = $('#div_id_email');
        if (isValidating) {
            $email
                .removeClass('has-error has-success')
                .addClass('has-warning');
            $email
                .find('.form-control-feedback')
                .removeClass('fa-check fa-remove')
                .addClass('fa-spinner fa-spin');
        } else {
            var inputClass = 'has-error',
                iconClass = 'fa-remove';
            if (regForm.emailDelayed.isValid() && regForm.email.isValid()) {
                inputClass = 'has-success';
                iconClass = 'fa-check';
            }
            $email.removeClass('has-warning').addClass(inputClass);
            $email
                .find('.form-control-feedback')
                .removeClass('fa-spinner fa-spin')
                .addClass(iconClass);
        }
    });
    newUser.setPhoneNumberInput('#id_phone_number');

});
