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

```commandline
ABDM_CLIENT_ID = '<Actual client ID>'
ABDM_CLIENT_SECRET = '<Actual client secret>'
ABDM_ABHA_URL = "https://healthidsbx.abdm.gov.in/api/"
ABDM_GATEWAY_URL = "https://dev.abdm.gov.in/gateway"
X_CM_ID = "sbx"
```

Projects that need to use the ABDM APIs, and therefore receive the token in restore response, should enable `restore_add_abdm_token` feature flag.
