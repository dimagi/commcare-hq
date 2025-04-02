import { TempusDominus } from '@eonasdan/tempus-dominus';

new TempusDominus(
    document.getElementById('js-id-timepicker'),
    {
        display: {
            theme: 'light',
            components: {
                calendar: false,
            },
        },
        localization: {
            format: 'LT',
        },
    },
);
