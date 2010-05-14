/*********************************************
* This creates a print view for a given page, by changing colors and hiding irreleant stuff
*
* To use, put the desired CSS changes & elements to hide in print_settings
*
* Then call this script from a control, eg <a href="javascript:print_view();" id="print-but">
* Make sure to keep ID "print-but"
*
*/

var print_settings = { 
	"css" : [
				["body", "background-color", "#fff"],
				["a","color", "#000"],
				[".top-bar", "background-color", "#fff"],
				["#header", "border-bottom-color", "#000"],
				["th", "background-color", "#fff"],
				[".clinic-name", "background-color", "#fff"],
				["#wrapper", "-moz-box-shadow", "none"],
				["#wrapper", "box-shadow", "none"]
			],
	"hide" : [".buttons", ".daterange_tabs"]
};

var normal_settings = { "css" : [], "show": print_settings["hide"]};

function print_view() {
	for (elem in print_settings["css"]) {
		i = print_settings["css"][elem];
		
		normal_settings["css"].push([i[0], i[1], $(i[0]).css(i[1])])
		$(i[0]).css(i[1], i[2]);
	}
	
	for (elem in print_settings["hide"]) {
		$(print_settings["hide"][elem]).hide();
	}

	// show print control 
	$("#print-but").html("Return to Normal View");
	$("#print-but").attr("href", "javascript: normal_view();");
	
	// delay print() one beat, so the printer dialog will appear only after the print layout rendered 
	setTimeout("print()", 700);
}

function normal_view() {
	for (elem in normal_settings["css"]) {
		i = normal_settings["css"][elem];
		$(i[0]).css(i[1], i[2]);
	}
	
	for (elem in normal_settings["show"]) {
		$(normal_settings["show"][elem]).show();
	}

	// show print control 
	$("#print-but").html("Print View");
	$("#print-but").attr("href", "javascript: print_view();");
}