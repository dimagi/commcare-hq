
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


function openCustomCCP(phoneNo) {
// This function opens a fresh instance of the CCP host container and passes in the 
// phone number to call as a URL parameter
	
	
	// *** START THIRD PARTY MODIFICATION BLOCK ***
	
		// cloudFrontDomain must be edited to reflect the appropriate tion CloudFront distro (test or prod).   

		const cloudFrontDomain = "https://d2f6atb849qzj5.cloudfront.net/nysdoh/";   // Test environment
		//const cloudFrontDomain = "https://d2f6atb849qzj5.cloudfront.net/nysdoh/";   // DOH production environment
		
		
		// This is the name of CCP host container html form
		const hostContainer = "nysdohCCP.html";
		
		// Name of the window 
		const windowName = "NYS Custom CCP";
		
	// *** END THIRD PARTY MODIFICATION BLOCK ***
	

	// Ensure a parameter was passed
	if (phoneNo == null || phoneNo == "") {
		window.alert("This contact does not seem to have a phone number associated with it.");
		return(false);
	};
			
	// Remove any formatting and charactors other than numbers
	const numberPattern = /\d+/g;
	const arrPhoneNo = phoneNo.match(numberPattern);	
	var   cleanPhoneNo = arrPhoneNo.join("");

	// Ensure we have at least 10 chars available and no more than 11
	if (cleanPhoneNo.length < 10 || cleanPhoneNo.length > 11) {
		window.alert("This contact does not seem to have a 10 digit local phone number associated with it: " + cleanPhoneNo);
		return(false);
	};

	// Strip out international prefixes if present
	const charOne = cleanPhoneNo.charAt(0);

	if (charOne == "0" || charOne == "1") {
		const stripPhoneNo = cleanPhoneNo.substring(1);
		cleanPhoneNo = stripPhoneNo;
	};
	
	// Ensure the content still looks like a 10 digit local phone number
	if (cleanPhoneNo.length != 10) {
		window.alert("This contact does not seem to have a dialable 10 digit local phone number associated with it: " + cleanPhoneNo);
		return(false);
	};
	
	// Build the URL
	const url = cloudFrontDomain + hostContainer + "?pn=" + cleanPhoneNo;
	
	var windowHdl = null;
	
	// Open the window
	windowHdl = window.open(url, windowName,"resizable=0,scrollbars=0,menubar=0,location=0,height=680px,width=1100px");
	
	if (windowHdl == null || windowHdl.closed) {
		window.alert("We were not able to open the CCP.  Perhaps your popup blocker is still on?");
		return(false);
	}

	return(true);

}
