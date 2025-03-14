import { TempusDominus } from '@eonasdan/tempus-dominus';
import '@eonasdan/tempus-dominus/dist/css/tempus-dominus.css';
import Alpine from 'alpinejs';

Alpine.directive('datepicker', (el, { expression }, { cleanup }) => {
    /**
     * To use, add x-datepicker to your input element.
     *
     *      <input x-datepicker="{% html_attr config %}" />
     *
     * This is especially useful in crispy forms for a CharField:
     *
     * self.helper.layout = crispy.Layout(
     *     ...
     *     crispy.Field(
     *         'modified_on',
     *         x_datepicker=json.dumps({
     *             ...
     *         }),
     *     ),
     *     ...
     * )
     */
    const config = expression ? JSON.parse(expression) : {};
    let components = {
        clock: false,
    };
    let localization = {
        format: 'yyyy-MM-dd',
    };

    if (config.datetime) {
        components = {
            seconds: true,
        };
        localization = {
            hourCycle: 'h23',
            format: 'yyyy-MM-dd H:mm:ss',
        };
    }

    const picker = new TempusDominus(el, {
        display: {
            theme: 'light',
            components: components,
        },
        localization: localization,
    });

    cleanup(() => {
        picker.dispose();
    });
});
