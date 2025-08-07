import { TempusDominus } from '@eonasdan/tempus-dominus';

new TempusDominus(
    document.getElementById('js-date-range'),
    {
        dateRange: true,
        multipleDatesSeparator: " - ",
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
