# VeriSlip courier payment-proof screening pilot

## Proposal status

This is an editable discussion draft for Sri Lankan courier operators, including
Domex, PromptX, and Koombiyo. It does not claim endorsement, partnership,
deployment, measured savings, or agreed commercial terms with any operator.

## Operating problem

For manual bank-transfer or COD-adjacent deliveries, a rider may receive a
payment screenshot while standing at the handover point. The operator needs a
fast, consistent instruction while retaining bank confirmation and cashier
escalation as the authoritative controls. VeriSlip supplies a screening signal;
it does not prove that funds settled.

## Existing integration surface

The current authenticated `POST /api/v1/courier/verify` endpoint accepts:

- `waybill_id`
- `expected_cod_amount` in LKR
- a base64 JPEG or PNG `slip_base64`
- optional `target_bank`

The response provides `can_handover_package`, `rider_action`, a safe cashier
alert, risk level/percentage, expected and detected amounts, mismatch status,
and a timestamp. The shared pipeline validates and sanitizes image bytes before
forensic processing. Existing middleware supplies API-key authentication,
tiered rate limiting, structured request logs, and correlation IDs.

## Proposed limited pilot

The operator selects one depot or route group and a defined rider cohort. Start
with shadow mode: riders follow current policy while VeriSlip records what it
would recommend. After the operator approves the shadow review, enable assisted
decisions with cashier escalation for every blocked or inconclusive result.

Before launch, agree the pilot duration, transaction cap, support hours,
escalation owner, outage procedure, retention period, permitted banks, success
thresholds, and stop rules. Do not change dispatch policy solely on the basis of
an unvalidated model score.

Suggested measures include eligible requests, completed screens, latency,
technical failures, amount mismatches, escalation rate, independently confirmed
false positives and false negatives, rider completion rate, and avoided-loss
scenarios. Report unconfirmed outcomes separately.

## ROI model

Use operator-supplied assumptions only:

```text
estimated avoided loss (LKR)
  = eligible transactions
  × confirmed fraud-attempt rate
  × average fraudulent order value (LKR)
  × measured intervention effectiveness
```

Run low, expected, and high scenarios. Keep every input visible. Subtract pilot
and operating costs separately if the operator wants net benefit. The model is
a planning estimate, not a promise. `core.research.courier_roi` implements the
same formula without embedded market figures.

## Security and privacy

Use separate scoped API keys per environment and operator, TLS, key rotation,
least-privilege access, bounded request sizes, and approved secrets management.
Do not log API keys or raw receipts. Send only the data required by the endpoint.
Agree data-controller/processor roles, incident contacts, retention, deletion,
and cross-border constraints before processing production customer material.

The current endpoint processes sanitized pixels in memory and returns a compact
decision response. Production deployment still requires operator-specific
threat modelling, load testing, monitoring, shared durable audit storage where
required, and a reviewed data-processing agreement.

## Decision and next steps

The operator should confirm the use case, supply baseline volumes and confirmed
fraud data, review the API/security pack, name business and technical owners,
and approve measurable pilot gates. Commercial pricing, service levels, and any
integration work remain subject to separate written agreement.

## Local validation

```cmd
python -m pytest tests\test_courier_pilot_proposal.py -v
python -m pytest tests\test_courier_api.py -v
```
