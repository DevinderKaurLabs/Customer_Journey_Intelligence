# Experiment design: does next-need targeting actually change behaviour?

The backtest in this repo answers **"can we predict the next need?"**
It does not answer **"does acting on that prediction make customers buy more, stay longer, or churn less?"**
Those are different questions. This page is the plan for the second one.

## Hypothesis

Customers in a detected life mission who receive stage-appropriate messages about their predicted next need
(and stop seeing ads for things they already bought) will show higher 60-day repeat purchase and spend than
customers who receive the current default (recently-viewed retargeting + generic promotions).

## Design

| | Control | Treatment |
|---|---|---|
| Who | Random 20% of customers with a detected mission | Remaining 80% |
| Ads | Current retargeting | Next-need creative; bought + fatigued products suppressed |
| CRM | Current calendar | Stage playbook (`actions.PLAYBOOK`) |
| Duration | 8 weeks | 8 weeks |

Randomise at customer level, **before** looking at stage, and stratify by mission and stage so both arms
have the same mix.

## Metrics

- **Primary:** 60-day repeat purchase rate.
- **Secondary:** 60-day spend per customer; number of distinct needs bought (journey depth);
  share of ad spend on already-bought products (should fall sharply in treatment).
- **Guardrails:** unsubscribe rate, complaint rate, margin (no discount creep).

## What would change our mind

- Treatment ≈ control on repeat rate → prediction is right but messaging doesn't move people; keep only
  the suppression rules (they save money regardless) and drop the rest.
- Gains only in one mission → keep the system narrow; don't scale the playbook to every mission.
- Spend up but margin down → the gain came from discounts, not relevance.

## Sample size (rule of thumb)

To detect a 2-point lift on a 25% repeat rate (25% → 27%) with 80% power at 5% significance you need
roughly **7,500 customers per arm**. Use the 80/20 split only if mission customers exceed ~37,500;
otherwise go 50/50.
