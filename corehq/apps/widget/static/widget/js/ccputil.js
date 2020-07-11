
// 	+-------------------------------------------------+
//   JavaScript to demonstrate a custom CCP container
//   form that can be invoked by a third party
//   application.     
//                                          
//			*** NOTE - SAMPLE CODE ONLY *** 
//
//   THE FILES IN THIS DISTRIBUTION ARE PROVIDED 
//	 STRICTLY AS SAMPLE CODE TO ILLUSTRATE CONCEPTS.
//	 THEY ARE PROVIDED ON AN "AS IS" BASIS WITH NO 
//	 WARRANTY OR FITNESS FOR PURPOSE IMPLIED.  
//	 CUSTOMERS MUST CAREFULLY EVALUATE THIS CODE FOR 
//	 SUITABILITY AND SECURITY CONSIDERATIONS PRIOR TO 
// 	 IMPLEMENTING IN A PRODUCTION OR OTHER CRITICAL
//	 ENVIRONMENT.

//   Author:  awscliff@                         
//   Version: 1.0                    
//   Date:    July 3, 2020        
// +-------------------------------------------------+  


var inCall = false;
const customCCPVersion = "NYSDOH 1.0";

function initializeCCP(instanceName) {
// This function excutes inline with the HTML <body> to initalize the CCP and set up event handlers
// for agent and contact events.
	
	var signInURL = "https://" + instanceName + ".awsapps.com/connect/login";
	var ccpPath = "https://" + instanceName + ".awsapps.com/connect/ccp-v2#/";
	
	document.getElementById("ConnectLogin").href = signInURL;            
	
	// Initialize the CCP into the container div
	
	connect.core.initCCP(divCCP, {
		ccpUrl:ccpPath,
		loginPopup: true,
		loginPopupAutoClose: true,
		softphone: {allowFramedSoftphone: true}
	});

	// agent events
	connect.agent(function(agent) { 
		
		var agentName = agent.getName();
		document.getElementById("divUserName").innerText = "Welcome, " + agentName;
		addToSystemLog("Agent is logged in: " + agentName);
		
		if (document.getElementById("chkAutoDial").checked) {
			dialEndPoint(document.getElementById('phoneNo').innerText);
		}
	});
	
	// contact events
	connect.contact(function(contact) {

		contact.onConnecting(function(contact) {

			document.getElementById("contactId").innerHTML = contact.getContactId();
			document.getElementById("queueName").innerHTML = contact.getQueue().name;
			document.getElementById("contactStatus").innerHTML = "Connecting...";
			addToSystemLog("Connecting to endpoint...");
			addToSystemLog("Unique Contact ID assigned: " + contact.getContactId());
			addToSystemLog("Call assigned to Queue: " + contact.getQueue().name);
			inCall = true;
			document.getElementById("phoneButton").disabled = true;
		});

		contact.onConnected(function(contact) {
			document.getElementById("contactStatus").innerHTML = "Connected";
			addToSystemLog("Call connected");
			inCall = true;
			document.getElementById("phoneButton").disabled = true;
		});
	
		contact.onEnded(function(contact) {
		//    var conStatus = document.getElementById("contactStatus").innerHTML;
		//	if (conStatus != "Disconnected") {
		//		window.alert("Your call has ended. Please close this window now.");    
		//	}
			document.getElementById("contactStatus").innerHTML = "Disconnected";
			document.getElementById("phoneButton").disabled = false;
			addToSystemLog("Call disconnected or cleared");
			inCall = false
		});
	});
}

function initDialer(phone, instanceName) {
// This function retrieves the phone number parameter (pn) from the URL passed by the
// calling application.

	addToSystemLog("Custom CCP Version: " + customCCPVersion);
	
	var phoneNo = "+1" + phone;
	
	document.getElementById("phoneNo").innerText = phoneNo;
	addToSystemLog("Phone number: (" + phoneNo + ") passed as URL parameter");
	
	// Check user preferences saved in a cookie and apply them to the check boxes

	getPref();
	
	if (document.getElementById("chkRestoreLocation").checked) {
	
		restoreLocation();
	}

	initializeCCP(instanceName);
}

function getPref() {
// This function reads the user preferences cookie 
	
	// Read the check box options
	var chkBox = checkCookie("checkBox");
	
	if (chkBox != "") {
		
		var c = chkBox.split("|");
		var l = c[0];
		var d = c[1];
		
		if (l == "ON") {
			document.getElementById("chkRestoreLocation").checked = true;
		} else {
			document.getElementById("chkRestoreLocation").checked = false;
		}
		
		if (d == "ON") {
			document.getElementById("chkAutoDial").checked = true;
		} else {
			document.getElementById("chkAutoDial").checked = false;
		}
	}
}

function restoreLocation() {
// This function restores the location of the window based on the last position saved

	// Read the window position cookie
	var windowLoc = checkCookie("windowLoc");
	
	if (windowLoc != "") {
		
		var leftTop = windowLoc.split("|");
		var x = leftTop[0];
		var y = leftTop[1];
		
		window.moveTo(x,y);
	}
	
	// Set up a hander to save the location when the form unloads
	window.onbeforeunload = function() {
		saveLocation();
		return(null);
	}
}

function saveLocation() {
// This function saves the current window location to a local cookie 
// The intent is to prevent the user from having to move the window to 
// their prefered location each time it opens.
		
	var winLoc = window.screenX + "|" + window.screenY;
	
	// Write cookie - 180 day expiry
	setCookie("windowLoc",winLoc,180);
	
}

function savePreferences() {
// This functions saves the users check box preferences

	var l = "OFF";
	var d = "OFF";
	
	if (document.getElementById("chkRestoreLocation").checked) {
	
		l = "ON";
	}

	if (document.getElementById("chkAutoDial").checked) {
	
		d = "ON";
	}
	
	var chk = l + "|" + d;
	
	// Write cookie - 180 day expiry
	setCookie("checkBox",chk,180);

	addToSystemLog("Preferences saved");
}

function dialEndPoint(targetEndPoint) {
// This function initiates an outbound dial to phone number endpoint passed
	
	addToSystemLog("Dialling: " + targetEndPoint);
		
	if (targetEndPoint == "" || targetEndPoint.includes("NOT")) {
		addToSystemLog("There is no valid phone number available");
		window.alert("There is no valid phone number available.");
		return(0);
	}
	
	if (document.getElementById("divUserName").innerText.includes("NOT")) {
		addToSystemLog("You have not logged in");
		window.alert("You have not logged in.");
		return(0);
	}

	if (inCall) {
		addToSystemLog("You already have an active call");
		window.alert("You already have an active call.");
		return(0);
	}
	
	connect.agent(function (agent){
		var endPoint = connect.Endpoint.byPhoneNumber(targetEndPoint);
		agent.connect(endPoint , {
			success : function(){addToSystemLog("Call to Connect endpoint API successful")},
            failure : function(){addToSystemLog("Call to Connect endpoint API failed")}
		});
	});	
}


function checkNetwork() {
// This function measures network performance on the UDP (media) ports hitting targets east and west
	
	addToSystemLog("[Check Network] button pressed");

	// Reset all states
	addToSystemLog("Resetting status lights");
	document.getElementById("imgUDPUSE1").src = "/static/widget/images/blackLED.png";
	document.getElementById("imgUDPUSW2").src = "/static/widget/images/blackLED.png";
	
	// UDP (media) ports
	testUDP();
	
}


function checkMedia() {
// This function evaluates media device and RTC availability

	addToSystemLog("[Check Media] button pressed");
	
    function onDetectRTCLoaded() {
                        
        if (DetectRTC.hasSpeakers) {
			document.getElementById("imgSpeakers").src = "/static/widget/images/greenLED.png";
			addToSystemLog("Speakers are present");
		}
		else {
			document.getElementById("imgSpeakers").src = "/static/widget/images/redLED.png";
			addToSystemLog("Speakers are not> present");
		}
		
        if (DetectRTC.hasMicrophone) {
			document.getElementById("imgMicrophone").src = "/static/widget/images/greenLED.png";
			addToSystemLog("Microphone is present");
		}
		else {
			document.getElementById("imgMicrophone").src = "/static/widget/images/redLED.png";
			addToSystemLog("Microphone is not present");
		}
		
        if (DetectRTC.isWebsiteHasMicrophonePermissions) {
			document.getElementById("imgMicrophonePermission").src = "/static/widget/images/greenLED.png";
			addToSystemLog("Microphone has access permission");
		}
		else {
			document.getElementById("imgMicrophonePermission").src = "/static/widget/images/redLED.png";
			addToSystemLog("Microphone does not have access permission");
		}
		
		if (DetectRTC.hasWebcam) {
			document.getElementById("imgWebCam").src = "/static/widget/images/greenLED.png";
			addToSystemLog("Web Cam is present");
		}
		else {
			document.getElementById("imgWebCam").src = "/static/widget/images/redLED.png";
			addToSystemLog("Web Cam is not present");
		}
				
        if (DetectRTC.isWebRTCSupported) {
			document.getElementById("imgWebRTC").src = "/static/widget/images/greenLED.png";
			addToSystemLog("Browser has RTC support");
		}
		else {
			document.getElementById("imgWebRTC").src = "/static/widget/images/redLED.png";
			addToSystemLog("Browser does not have RTC support");
		}

    }

	function reloadDetectRTC(callback) {
        DetectRTC.load(function() {
            onDetectRTCLoaded();

            if(callback && typeof callback == 'function') {
				callback();
            }
        });
    }

    DetectRTC.load(function() {
		reloadDetectRTC();
       // onDetectRTCLoaded();
    });
}

function setCookie(cname, cvalue, exdays) {
// This function writes a cookie.  Used to store the window location
 
	var d = new Date();
	d.setTime(d.getTime() + (exdays*24*60*60*1000));
	var expires = "expires="+ d.toUTCString();
	document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

function checkCookie(attrib) {
//This function evaluates the value of a single cookie attribute

	var attribVal=getCookie(attrib);
	if (attribVal != "") {
		return(attribVal);
  } else {
		return("");
  }
}

function getCookie(cname) {
//This function reads cookie attribute values

  var name = cname + "=";
  var decodedCookie = decodeURIComponent(document.cookie);
  var ca = decodedCookie.split(';');
  for(var i = 0; i <ca.length; i++) {
    var c = ca[i];
    while (c.charAt(0) == ' ') {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return c.substring(name.length, c.length);
    }
  }
  return "";
}

function addToSystemLog(logTxt) {
// This function adds an entry to the on screen diagnostic log table

	// Create the new event container
	var newContainer = document.createElement("DIV");
	
	// Assign the correct class
	newContainer.className = "eventContainer";
	
	// Attach it to the parent
	document.getElementById("divEventWindow").appendChild(newContainer); 
	
	
	// Create the new date div 
	var newDate = document.createElement("DIV");

	// Assign the correct class
	newDate.className = "eventDate";
	
	// Assign a value
	
	var d = getFormattedDate();
	newDate.innerHTML = d;
	
	// Attach it to the parent
	newContainer.appendChild(newDate);
	
	
	// Create the new text div
	var newText = document.createElement("DIV");
	
	// Assign the correct class
	newText.className = "eventText";
	
	// Assign a value
	newText.innerHTML = logTxt;
	
	// Attach it to the parent
	newContainer.appendChild(newText);

}

function getFormattedDate() {
// This function returns a formatted date for use in the log table

	var d = new Date();

	var month=new Array();
	month[0]="Jan";
	month[1]="Feb";
	month[2]="Mar";
	month[3]="Apr";
	month[4]="May";
	month[5]="Jun";
	month[6]="Jul";
	month[7]="Aug";
	month[8]="Sep";
	month[9]="Oct";
	month[10]="Nov";
	month[11]="Dec";

	var hours = d.getHours();
	var minutes = d.getMinutes();
	var seconds = d.getSeconds();
  
	if (minutes < 10) {
		minutes = "0" + minutes;
	}

	if (seconds < 10) {
		seconds = "0" + seconds;
	}
  
	var strTime = hours + ":" + minutes + ":" + seconds;
    var strDate = strTime + " " + d.getDate() + "-" + month[d.getMonth()];
	return(strDate);
}

function copyToClipboard() {
// This function saves the text elements of the log table to the clipboard object

	// The DOM consists of an event container div with two divs within it  - date and content

	var txt = "";
	
	// Get the Parent div
	var p = document.getElementById("divEventWindow");
	
	// Get the children of this div, this will return a collection of divs that contain
	// each message
	var c = p.children;
	
	// Loop each continer div	
	var i;
	var eventTxt = ""
	for (i = 0; i < c.length; i++) {
		
		eventTxt = "";
		
		// Now get the two div elements within this container
		var e = c[i].children;
		
		eventTxt = e[0].innerHTML;   //  This is the date
		eventTxt += "\t";			 //  TAB Char	
		eventTxt += e[1].innerHTML;  //  This is the message body
		eventTxt += "\n";			 //  CRLF	
		txt += eventTxt;
	}

	navigator.clipboard.writeText(txt).then(function() {
		// clipboard successfully set 
		window.alert("Event log has been copied to the system Clipboard");
	}, function(err) {
		// clipboard write failed 
		window.alert("Could not access the system Clipboard: " + err);
	});

}
