# Overview

## ABDM
ABDM stands for Ayushman Bharat Digital Mission. It is a flagship program launched by the Indian government to provide universal health coverage to its citizens through digital means. The program aims to build a digital health ecosystem in India, enabling efficient delivery of health services and access to health records.

## ABHA
ABHA stands for Ayushman Bharat Health Account, and it is a unique 14-digit identification number that is used to identify individuals within India's digital healthcare ecosystem. ABHA helps individuals to digitize their health records and manage their healthcare needs better. ABDM provides facilities such as hospital discovery, faster appointment booking, and other services through ABHA. The ABHA number is used to authenticate individuals and thread their health records across multiple systems and stakeholders, with the informed consent of the patient.


# Technical Details

## Milestones
ABDM program has three milestones, which are referred to as Milestone 1, Milestone 2, and Milestone 3. To obtain a certificate and production keys, the functionality of the system is demonstrated to a panel of ABDM experts at each phase.

Within code, relevant logic is divided into milestones under respective python modules. E.g. custom/abdm/milestone_one


## Setup
When HQ system is installed, following entries should be added in `localsettings.py` in order for ABDM APIs to work:
Note: Below example with values are from ABDM Sandbox environment

```commandline
ABDM_CLIENT_ID = '<Actual client ID>'
ABDM_CLIENT_SECRET = '<Actual client secret>'
ABDM_X_CM_ID = 'sbx'
ABDM_ABHA_URL = "https://healthidsbx.abdm.gov.in/api/"
ABDM_GATEWAY_URL = "https://dev.abdm.gov.in/gateway"
```

Projects that need to use the ABDM APIs, and therefore receive the token in restore response, should enable `restore_add_abdm_token` feature flag.


### Error Response Format

ABDM Gateway uses a custom response format in case of errors. This is true for both APIs exposed by them and APIs consumed by them from HIU/HIP server to send callback responses.
It is also applicable to all types of error types -  client(4xx), server(5xx), unhandled exceptions.

Here is a sample format.
```json
{
    "error": {
        "code": 4400,
        "message": "Required attributes not provided or Request information is not as expected",
    }
}
```
We aim to keep this format consistent for both APIs exposed to hiu/hip client and gateway.
We use [drf_standardized_errors](https://github.com/ghazi-git/drf-standardized-errors/) to achieve a standard response format for all the error types. Bonus - It also neatly formats validation errors when they are multiple.

> TODO - Add this package to requirememts when this is isolated in different repostiory.

Then we customize the response obtained from `drf_standardized_errors` to the above format.
A field `details` is also included that provides additional details about the errors occurred.

> Note: Field `details` can have multiple items for Validation errors.

> Note: Field `details` is not sent out for APIs exposed to ABDM Gateway.

Sample Error Formats:

a. Validation Error
```json
{
    "error": {
        "code": 4400,
        "message": "Required attributes not provided or Request information is not as expected",
        "details": [
            {
                "code": "required",
                "detail": "This field is required.",
                "attr": "purpose.code"
            }
        ]
    }
}
```

b. Authentication Failed Error
```json
{
    "error": {
        "code": 4401,
        "message": "Unauthorized request",
        "details": [
            {
                "code": "authentication_failed",
                "detail": "Unauthorized",
                "attr": null
            }
        ]
    }
}
```
