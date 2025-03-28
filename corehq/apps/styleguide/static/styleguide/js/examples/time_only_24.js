import '@popperjs/core/dist/umd/popper.min';
import '@eonasdan/tempus-dominus/dist/js/tempus-dominus.min';

new tempusDominus.TempusDominus(
    document.getElementById('js-id-timepicker-24'),
    {
        display: {
            theme: 'light',
            components: {
                calendar: false,
            },
        },
        localization: {
            hourCycle: 'h23',
            format: 'H:mm',
        },
    },
);
