CommTrack
=========

What happens during a CommTrack submission?
-------------------------------------------

This is the life-cycle of an incoming stock report via sms.

1. SMS is received and relevant info therein is parsed out

2. The parsed sms is converted to an HQ-compatible xform submission. This includes:

  * stock info (i.e., just the data provided in the sms)
  * location to which this message applies (provided in message or associated with sending user)
  * standard HQ submission meta-data (submit time, user, etc.)

  Notably missing: anything that updates cases

3. The submission is *not* submitted yet, but rather processed further on the server. This includes:

  * looking up the product sub-cases that actually store stock/consumption values.
    (step (2) looked up the location ID; each supply point is a case associated with that location, and actual stock data is stored in a sub-case -- one for each product -- of the supply point case)
  * applying the stock actions for each product in the correct order
    (a stock report can include multiple actions; these must be applied in a consistent order or else unpredictable stock levels may result)
  * computing updated stock levels and consumption (using somewhat complex business and reconciliation logic)
  * dumping the result in case blocks (added to the submission) that will update the new values in HQ's database
  * post-processing also makes some changes elsewhere in the instance, namely:
     * also added are 'inferred' transactions (if my stock was 20, is now 10, and i had receipts of 15, my inferred consumption was 25). This is needed to compute consumption rate later. Conversely, if a deployment tracks consumption instead of receipts, receipts are inferred this way.
     * transactions are annotated with the order in which they were processed

  Note that normally CommCare generates its own case blocks in the forms it submits.

4. The updated submission is submitted to HQ like a normal form


Submitting a stock report via CommCare
--------------------------------------

CommTrack-enabled CommCare submits xforms, but those xforms **do not** go through the post-processing step in (3) above.
Therefore these forms must generate their own case blocks and mimic the end result that commtrack expects.
This is severely lacking as we have not replicated the full logic from the server in these xforms (unsure if that's even possible, nor do we like the prospect of maintaining the same logic in two places), nor can these forms generate the inferred transactions.
As such, the capabilities of the mobile app are greatly restricted and cannot support features like computing consumption.

This must be fixed and it's really not worth even discussing much else about using a mobile app until it is.
