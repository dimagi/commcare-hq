(function($) {
    $.calendars.calendars.ethiopian.prototype.regionalOptions[''] = {
		name: 'Ethiopian',
		epochs: ['BEE', 'EE'],
		monthNames: ['Meskerem', 'Tikemet', 'Hidar', 'Tahesas', 'Tir', 'Yekatit',
				     'Megabit', 'Miazia', 'Genbot', 'Sene', 'Hamle', 'Nehase', 'Pagume'],
		monthNamesShort: ['Mes', 'Tik', 'Hid', 'Tah', 'Tir', 'Yek',
				          'Meg', 'Mia', 'Gen', 'Sen', 'Ham', 'Neh', 'Pag'],
		dayNames: ['Ehud', 'Segno', 'Maksegno', 'Irob', 'Hamus', 'Arb', 'Kidame'],
		dayNamesShort: ['Ehu', 'Seg', 'Mak', 'Iro', 'Ham', 'Arb', 'Kid'],
		dayNamesMin: ['Eh', 'Se', 'Ma', 'Ir', 'Ha', 'Ar', 'Ki'],
		digits: null,
		dateFormat: 'dd/mm/yyyy',
		firstDay: 0,
		isRTL: false
    };


    $.calendarsPicker.regionalOptions[''] = { // Default regional settings - English/US
		renderer: $.calendarsPicker.regionalOptions[''].renderer, // this.defaultRenderer
		prevText: '&lt;PrevMonth',
		prevStatus: 'Show the previous month',
		prevJumpText: '&lt;&lt;',
		prevJumpStatus: 'Show the previous year',
		nextText: 'Next&nbsp;Month&gt;',
		nextStatus: 'Show the next month',
		nextJumpText: '&gt;&gt;',
		nextJumpStatus: 'Show the next year',
		currentText: 'Current',
		currentStatus: 'Show the current month',
		todayText: 'Today',
		todayStatus: 'Show today\'s month',
		clearText: 'Clear',
		clearStatus: 'Clear all the dates',
		closeText: 'Close',
		closeStatus: 'Close the datepicker',
		yearStatus: 'Change the year',
		earlierText: '&#160;&#160;▲',
		laterText: '&#160;&#160;▼',
		monthStatus: 'Change the month',
		weekText: 'Wk',
		weekStatus: 'Week of the year',
		dayStatus: 'Select DD, M d, yyyy',
		defaultStatus: 'Select a date',
		isRTL: false
	};


	$.calendars.calendars.ethiopian.prototype.regionalOptions.am = {
		name: 'የኢትዮጵያ ዘመን አቆጣጠር',
		epochs: ['BEE', 'EE'],
		monthNames: ['መስከረም', 'ጥቅምት', 'ኅዳር', 'ታህሣሥ', 'ጥር', 'የካቲት',
		             'መጋቢት', 'ሚያዝያ', 'ግንቦት', 'ሰኔ', 'ሐምሌ', 'ነሐሴ', 'ጳጉሜ'],
		monthNamesShort: ['መስከ', 'ጥቅም', 'ኅዳር', 'ታህሣ', 'ጥር', 'የካቲ',
		                  'መጋቢ', 'ሚያዝ', 'ግንቦ', 'ሰኔ', 'ሐምሌ', 'ነሐሴ', 'ጳጉሜ'],
		dayNames: ['እሑድ', 'ሰኞ', 'ማክሰኞ', 'ረቡዕ', 'ሓሙስ', 'ዓርብ', 'ቅዳሜ'],
		dayNamesShort: ['እሑድ', 'ሰኞ', 'ማክሰ', 'ረቡዕ', 'ሓሙስ', 'ዓርብ', 'ቅዳሜ'],
		dayNamesMin: ['እሑ', 'ሰኞ', 'ማክ', 'ረቡ', 'ሐሙ', 'ዓር', 'ቅዳ'],
		digits: null,
		dateFormat: 'dd/mm/yyyy',
		firstDay: 0,
		isRTL: false
	};
})(jQuery);
