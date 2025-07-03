import { TempusDominus } from '@eonasdan/tempus-dominus';

new TempusDominus(
    document.getElementById('js-dateonly'),
    {
        display: {
            theme: 'light',
            components: {
                clock: false,
            },
        },
        localization: {
            format: 'L',
        },
    },
);
