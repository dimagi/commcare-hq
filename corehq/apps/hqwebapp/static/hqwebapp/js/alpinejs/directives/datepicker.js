import { TempusDominus } from '@eonasdan/tempus-dominus';
import '@eonasdan/tempus-dominus/dist/css/tempus-dominus.css';
import Alpine from 'alpinejs';
import _ from 'underscore';

const defaultTranslations = {
    clear: gettext('Clear selection'),
    close: gettext('Close the picker'),
    dayViewHeaderFormat: { month: gettext('long'), year: gettext('2-digit') },
    decrementHour: gettext('Decrement Hour'),
    decrementMinute: gettext('Decrement Minute'),
    decrementSecond: gettext('Decrement Second'),
    incrementHour: gettext('Increment Hour'),
    incrementMinute: gettext('Increment Minute'),
    incrementSecond: gettext('Increment Second'),
    nextCentury: gettext('Next Century'),
    nextDecade: gettext('Next Decade'),
    nextMonth: gettext('Next Month'),
    nextYear: gettext('Next Year'),
    pickHour: gettext('Pick Hour'),
    pickMinute: gettext('Pick Minute'),
    pickSecond: gettext('Pick Second'),
    previousCentury: gettext('Previous Century'),
    previousDecade: gettext('Previous Decade'),
    previousMonth: gettext('Previous Month'),
    previousYear: gettext('Previous Year'),
    selectDate: gettext('Select Date'),
    selectDecade: gettext('Select Decade'),
    selectMonth: gettext('Select Month'),
    selectTime: gettext('Select Time'),
    selectYear: gettext('Select Year'),
    today: gettext('Go to today'),
    toggleMeridiem: gettext('Toggle Meridiem'),
};

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
        localization: _.extend(defaultTranslations, localization),
    });

    cleanup(() => {
        picker.dispose();
    });
});
