import '@popperjs/core/dist/umd/popper.min';
import '@eonasdan/tempus-dominus/dist/js/tempus-dominus.min';

new tempusDominus.TempusDominus(
    document.getElementById('js-date-range'),
    {
        dateRange: true,
        multipleDatesSeparator: " - ",
        display: {
            theme: 'light',
            components: {
                clock: false,
            }
        },
        localization: {
            format: 'L',
        },
    },
);
