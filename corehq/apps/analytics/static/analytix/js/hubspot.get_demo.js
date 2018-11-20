/* global window */
$(function () {
  'use strict';

  hqImport("analytix/js/hubspot").then(function () {
    var hubspot_get = hqImport('analytix/js/initial').getFn('hubspot'),
        hubspot_api_id = hubspot_get('apiId');

    // Old (control) hubspot form:
    hbspt.forms.create({
      portalId: hubspot_api_id,
      formId: "0f5de42e-b562-4ece-85e5-cfd2db97eba8",
      target: "#get-demo-cta-form-body",
      css: ""
    });

    // New (variant A) hubspot form:
    hbspt.forms.create({
      portalId: hubspot_api_id,
      formId: "38980202-f1bd-412e-b490-f390f40e9ee1",
      target: "#get-demo-cta-form-content",
      css: "",
      onFormSubmit: function ($form) {
        $('#get-demo-cta-calendar-content').fadeIn();
        $('#get-demo-cta-form-content').addClass('hide');
        var email = $form.find('[name="email"]').val(),
            firstname = $form.find('[name="firstname"]').val(),
            lastname = $form.find('[name="lastname"]').val(),
            newUrl = document.location.href + '?email=' + email + '&name=' + firstname + '%20' + lastname;

        window.history.pushState(
            "dimagi-contact-url " + document.title, document.title, newUrl
        );

        $.getScript('//cdn.scheduleonce.com/mergedjs/so.js');

      },
    });
  });

});
