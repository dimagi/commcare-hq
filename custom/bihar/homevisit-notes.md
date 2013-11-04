# Homevisit
## Done/Due

## New Spec

1) Need to look at visits in pairs
- If DUE, then look for DONE
- can be multiple DUE/DONE pairs in time window for one case
- if DUE in window, can look for DONE within +/-10days of DUE, otherwise not counted as DONE in time window
- don't count DONE visits in window if no corresponding DUE visit

2) How define DUE?
- search all forms of type Y submitted in last 120 days with date_next_X falling within last 30 days
- (2nd trimester additional criteria (94 <= edd - date_next_bp < 187) )
- (3rd trimester additional criteria (edd - date_next_bp < 94) )

3) How define DONE?
- search all forms of type Y submitted in last 120 days with date_next_X falling within last 30 days AND has a subsequent form of type X submitted within last 40 days
- from this subsequent form, record days_visit_overdue

4) Definition of X and Y
- if X = BP, Y = Reg, BP
- if X = PNC, Y = Reg, Delivery, PNC
- if X = EBF, Y = Reg, Delivery, PNC, EBF
- if X = CF, Y = Reg, Delivery, PNC, EBF, CF


Everything below here is considered deprecated

## Old spec

Note: all 'form' properties are actually located in the form's case block:
e.g. `date_next_bp` means `case/update/date_next_bp`,
and `date_modified` means `case/@date_modified`.

### 2nd Trimester Birth Preparedness Visits
`bp2` *BP (2nd Tri) Visits*

- *Filter*. **BP** or **Reg** forms where
  - `94 <= case.edd - date_modified < 187`
- *Denom*. Number of forms where all of the following hold:
  - `date_next_bp` not blank
  - `date_next_bp` in last 30 days
- *Num*. Number of **BP** forms where all of the following hold:
  - `days_visit_overdue` not blank
  - `days_visit_overdue` = 0

### 3rd Trimester Birth Preparedness Visits
`bp3` *BP (3rd Tri) Visits*

Same as `bp2` except:
- *Filter*. **BP** or **Reg** forms where
  - `case.edd - date_modified < 94`

### Post Natal Care Visits
`pnc` *PNC Visits*

- *Filter*. **Del**, **PNC**, or **Reg** forms
- *Denom*. Number of forms where all of the following hold:
  - `date_next_pnc` not blank
  - `date_next_pnc` in last 30 days
- *Num*. **PNC** forms where all of the following hold:
  - `days_visit_overdue` not blank
  - `days_visit_overdue` = 0, 1, or -1

### Exclusive Breastfeeding Visits
`ebf` *EBF Visits*

- *Filter*. **Del**, **PNC**, **Reg**, or **EBF** forms
- *Denom*. Number of forms where all of the following hold:
  - `date_next_eb` not blank
  - `date_next_eb` in last 30 days
- *Num*. Number of **EBF** forms where all of the following hold:
  - `days_visit_overdue` not blank
  - `days_visit_overdue` = 0, 1, or -1

### Complementary Feeding  Visits
`cf` *CF Visits*

- *Filter*. **Del**, **PNC**, **Reg**, **EBF**, or **CF** forms
- *Denom*. Number of forms where all of the following hold:
  - `date_next_cf` not blank
  - `date_next_cf` in last 30 days
- *Num*. Number of **CF** forms where all of the following hold:
  - `days_visit_overdue` not blank
  - `days_visit_overdue` = 0, 1, or -1
