/* global ko */
/* global django */

ko.validation.rules['phone_number_val'] = {
    validator: function (val) {
    console.log(val == 5)
    return val == 5;
      // if (input.value.trim()) {
      //   if ($(this).intlTelInput("isValidNumber")) {
      //     validMsg.classList.remove("hide");
      //   } else {
      //     input.classList.add("error");
      //     var errorCode = $(this).intlTelInput("getValidationError");
      //     errorMsg.innerHTML = errorMap[errorCode];
      //     errorMsg.classList.remove("hide");
      //   }
      // }
      },

    message: django.gettext("Please enter a valid phone number."),

};

ko.validation.registerExtenders();
