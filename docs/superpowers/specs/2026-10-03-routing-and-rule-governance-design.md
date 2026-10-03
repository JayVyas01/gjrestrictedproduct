# Severity Routing, Buyer Stock Limit and Rule Governance (Revision 4)

**Status:** draft for review · **Date:** 2026-10-03 · **Parent spec:** [licence types and demo design](2026-09-28-licence-types-and-demo-design.md) §5b (this revision amends it)

## 1. What changes and why

| # | Owner decision (2026-10-03) | Replaces |
|---|---|---|
| R1 | **The buyer's stock limit is the buyer's call.** If a sale would take the buyer above their stock limit, the seller's start is **not** refused. The request goes to the buyer, who can only reject it. | §5b check "buyer's stock plus quantity stays within `max_stock_qty`" at creation. That check leaked the buyer's stock to the seller. |
| R2 | A stock-limit rejection raises **no authority alert** and **does not count** toward the seller's 30-day rejection pattern. | §5a: every buyer rejection alerts |
| R3 | **Severity routing.** Configurable **quantity thresholds** per substance or class decide the approval chain. At or below the threshold, the area officer approves. Above it, the **area officer and then the superintendent** both approve, in that order. | §5b: the designated officer is always the only approver |
| R4 | Approval levels are **taluka and district only** for now. The level is stored as data, so another level can be added later without rework. | — |
| R5 | **Superintendent-approved transactions in oversight** stay in the superintendent's batch, marked "Approved by you". The superintendent **cannot flag** them. The Head Authority's overview lists them. | — |
| R6 | **Rule governance (maker-checker).** The Licensing Authority, superintendents (holders of a district position) and the Head Authority can **draft** changes: new licence types, rule versions and approval thresholds. A **Head Authority** user who is not the drafter **approves** each change with a one-time code, and only then does it take effect. | §2 D-R12: catalogue writes go only through Licensing Authority services |

## 2. R1–R2: buyer stock limit

- `start_transaction` and the new dry-run check (D3 B4) **drop the buyer stock-limit check**. All other checks stay, including the buyer's per-transaction limit, which is a property of the licence type and not private business data.
- **Buyer view.** While the transaction waits for the buyer, the detail adds `stock_limit_problem`, which only the buyer sees. For example: "Confirming would take your Whisky stock to 450 L, above your licence limit of 400 L. You can only reject this sale." In that state `allowed_outcomes` is `["REJECT"]`.
- **Confirm refused.** A confirm that would breach the limit gets a 422 with the same sentence. The check runs again under the user lock when the confirm happens.
- **Reject.** A new seeded reason, `BUYER / STOCK_LIMIT` ("This would take me over my licence's stock limit"), is filled in automatically in the stock-limit state. Choosing it **raises no alert**, and `pattern_count` **excludes** it (alerts query by reason code).
- **The seller sees** "Rejected by the buyer: over the buyer's stock limit", with no numbers.
- **Approval** still re-checks the buyer's cap under the balance locks, so stock can't change between confirm and approval. Only officers see that refusal, and they may see the numbers.

## 3. R3–R5: severity routing

### Model
- `catalogue.ApprovalThreshold` covers exactly one substance or one class, the same pattern as `LicenceTypeRule`.
- `catalogue.ApprovalThresholdVersion` is append-only and versioned (`superintendent_above_qty` > 0, unit taken from the scope).
- Resolving a threshold works like resolving a rule: a substance threshold beats its class threshold. **With no threshold, the officer alone approves**, so every existing transaction keeps working.
- `Transaction.approval_chain` is fixed when the transaction is created, and later threshold changes don't move transactions already in flight. It takes one of two values:
  - `OFFICER`
  - `OFFICER_THEN_SUPERINTENDENT`
- The superintendent position is already stored on every transaction.

### States

```
AWAITING_BUYER → AWAITING_OFFICER → APPROVED                                   (chain OFFICER)
AWAITING_BUYER → AWAITING_OFFICER → AWAITING_SUPERINTENDENT → APPROVED         (chain OFFICER_THEN_SUPERINTENDENT)
             ↘ REJECTED_BY_BUYER     ↘ REJECTED_BY_OFFICER   ↘ REJECTED_BY_SUPERINTENDENT
AWAITING_BUYER → CANCELLED (seller)
```

### Decisions and stock
- A new `DecisionStep.SUPERINTENDENT` step is signed with a `DECISION` code. Only the current holder of the transaction's superintendent position can take it.
- An officer decision on a two-step chain is "Recommend approval" or "Reject": the officer's approval moves no stock and sets `AWAITING_SUPERINTENDENT`. Only the **final** approval re-runs every check and moves stock, using the same rules as today (eligibility, limits, seller stock, buyer cap under lock).
- A superintendent rejection needs an officer-kind reason, and "Other" needs text.
- The timeline shows both approvals: each position and who held it.
- Owner decision (2026-10-04, replaces the separation-of-duties rulings C-R2/C-R5): a superintendent's approval is enough. An officer who also holds the transaction's superintendent position approves both levels in one signed step (APPROVE or REJECT at the officer step; APPROVE writes an officer RECOMMEND and a superintendent APPROVE with the same code and moves stock). An officer who recommended and is then given the superintendent position may give the final approval. The Head Authority reviews superintendent-approved items in oversight.

### Oversight (R5)
- The batch keeps all approved transactions.
- The batch item presenter adds `approved_by_superintendent`. `flag_item` refuses those items with "You approved this transaction; the Head Authority reviews it."
- The Head Authority overview filters on `GET /api/transactions?approved_by=superintendent`.
- A flag on an officer-only transaction still alerts the approving officer's position.

### Alerts
- A buyer rejection, except a stock-limit one, alerts the officer and superintendent positions, as now.
- A rejection or flag needs no new alert kind.

## 4. R6: rule governance

### Model
`catalogue.RuleChangeProposal` stores:
- `kind`, one of `NEW_LICENCE_TYPE`, `RULE_VERSION` and `APPROVAL_THRESHOLD`
- `payload`, a JSON object checked against a per-kind serializer
- `drafted_by`, `drafted_at` and `justification` (required)
- `status`, one of `SUBMITTED`, `APPROVED`, `REJECTED` and `WITHDRAWN`
- `decided_by`, `decided_at` and `decision_note`
- `applied_ref`, the ID of the version or type it created

Rows can only change their status and decision fields, using the same RLS and update pattern as transactions. All writes run as SYSTEM after a who-may-act check in the service.

### Who may act
- **Draft:** the Licensing Authority, a Personnel user who currently holds a **district** position, or the Head Authority.
- **Approve or reject:** a Head Authority user who is **not the drafter**. Approval needs a `DECISION` code, and so does a rejection, so both are attributable.
- **Withdraw:** the drafter, while the proposal is `SUBMITTED`.
- **Read:**
  - each drafter reads their own proposals
  - the Head Authority, Software Owner and Licensing Authority read all of them

### Applying a change
- Approval applies the change through the existing `catalogue.service` functions (`add_rule_version`, plus new `add_licence_type` and `add_threshold_version`) in the same transaction.
- If applying fails, everything rolls back and the proposal stays `SUBMITTED`, so it is all or nothing.
- **Existing licences don't change** (permissions stay frozen, §2 D3). Thresholds apply only to new transactions.
- **Audit events** carry IDs only:
  - `rule_change.drafted`
  - `rule_change.approved` / `.rejected` / `.withdrawn`
  - `catalogue.*` for the applied write

### Lock order
user row → OTP challenge → proposal row → catalogue row (the rule or threshold `select_for_update`) → audit

## 5. Milestones (re-cut)

| # | Milestone | Contents |
|---|---|---|
| **D2c** | Routing and buyer stock limit (backend) | R1–R5: thresholds (seeded, read API), approval chain, superintendent step, stock-limit reject, oversight marking. D3 APIs B1–B4 and B6. |
| **D2d** | Rule governance and register APIs (backend) | R6 proposals (draft, withdraw, approve or reject with a code, apply). D3 APIs B7–B8 (licence register, licence types, review settings). |
| **D3** | Web app | Every screen in the D3 design, plus: the superintendent approval step, the buyer's "only reject" state, and the screens for drafting and approving rule changes (Licensing Authority, superintendent and Head Authority). |
| **D4** | Demo tooling | Unchanged. The seed adds one threshold (Whisky above 200 L needs the superintendent), so the demo can show both chains. |

## 6. Testing (each with plain-language messages)

- **Routing:**
  - the threshold picks the chain
  - a substance threshold beats its class
  - with no threshold the officer alone approves
  - the chain is fixed when the transaction is created
- **Two-step chain:**
  - the officer recommends and nothing moves
  - the superintendent approves and stock moves
  - a superintendent rejection is final
  - only the current holder can act
  - approval re-checks everything
- **Buyer stock limit:**
  - the start is not refused
  - the seller sees no numbers
  - the buyer can only reject
  - confirm gets a 422
  - no alert is raised and the pattern doesn't count it
- **Oversight:** superintendent-approved items are marked and can't be flagged; the Head Authority's filter finds them.
- **Governance:**
  - each role can draft or not as listed
  - the drafter cannot approve their own proposal
  - approval needs a valid code
  - applying is all or nothing
  - frozen licences are unaffected
  - proposals can't be edited after a decision
  - RLS read rules hold
  - the audit trail is complete
