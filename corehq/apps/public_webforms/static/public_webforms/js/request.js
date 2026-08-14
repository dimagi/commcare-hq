import 'commcarehq';

import $ from 'jquery';
import Alpine from 'alpinejs';
import intlTelInput from 'intl-tel-input/build/js/intlTelInput.min';

Alpine.start();

document.addEventListener('DOMContentLoaded', () => {
    const phoneNumber = document.getElementById('id_phone_number');
    if (!phoneNumber) {
        return;
    }

    const widget = intlTelInput(phoneNumber, {
        containerClass: 'w-100',
        separateDialCode: true,
        loadUtils: () => import('intl-tel-input/utils'),
    });

    phoneNumber.addEventListener('focus', () => {
        $.get('https://ipinfo.io', function () {}, 'jsonp').always(function (resp) {
            if (resp && resp.country && !phoneNumber.value) {
                widget.setCountry(resp.country);
            }
        });
    }, {once: true});
});
