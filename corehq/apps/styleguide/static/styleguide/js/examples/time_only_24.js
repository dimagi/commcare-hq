import { TempusDominus } from '@eonasdan/tempus-dominus';

new TempusDominus(
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
