# Research Audit

## Executive summary

Ike is strongest as a workflow product, not as a generic AI writer.
Its clearest market value is combining:

- topic discovery
- editorial framing
- evidence-aware scripting workflow
- human approvals

The product is already much more defensible than "one-click AI script" tools, but it is not yet broad self-serve SaaS.
Right now it is best positioned for:

- design-partner pilots
- small editorial teams
- producer-led economics or geopolitics channels

The biggest remaining weakness is not visual polish.
It is trust infrastructure:

- source traceability
- role controls
- deeper competitor ingestion
- stronger multi-user auditability

## Why this product should exist

Economics YouTube content is unusually fragile:

- topics age quickly
- facts must be checkable
- titles and packaging matter
- scripts need both rigor and entertainment value

Official YouTube guidance makes clear that creators need to think in terms of packaging, impressions, CTR, retention, and audience segments rather than only topic choice.
That means a serious editorial team needs a system that joins:

- topic opportunity detection
- packaging hypothesis
- retention-aware scripting
- review and approvals

This product exists because generic creator tools and generic AI writers do not combine those layers in one workflow.

## Who it is for

Best-fit user:

- producer
- editor
- channel operator

Best-fit buyer:

- channel owner
- studio lead
- newsletter + YouTube founder
- small agency running 1-5 research-heavy channels

Best-fit use cases:

- macroeconomics channels
- economic-political explainer channels
- serious business channels with weekly longform uploads

Weak fit:

- entertainment Shorts factories
- meme/news clipping channels
- solo beginners with low publishing discipline

## Current market comparison

### vidIQ

Strong at:

- creator growth tooling
- ideas, trends, optimization, AI coach

Weak relative to Ike:

- not a structured editorial artifact pipeline
- not specialized for economics research workflow

Official page shows trend research, ideas, AI credits, and enterprise/team offerings.
Source: https://vidiq.com/plans/

### Exploding Topics

Strong at:

- discovering early trends
- trend database and forecasting

Weak relative to Ike:

- not a scripting workflow
- not human editorial orchestration
- not economics-channel specific

Official pricing and positioning show trend discovery and monitoring, not editorial pipeline execution.
Source: https://explodingtopics.com/pricing

### BuzzSumo

Strong at:

- content discovery
- monitoring
- research
- YouTube analyzer at higher tiers

Weak relative to Ike:

- oriented more toward broad marketing and PR
- not built as a script-production operating system

Source: https://buzzsumo.com/pricing/

### TubeBuddy

Strong at:

- creator optimization and channel management
- topical analysis
- competitor alerts
- retention and SEO support

Weak relative to Ike:

- not a deep human-in-the-loop editorial production workflow
- not aimed at research-heavy economics scripting teams

Source: https://www.tubebuddy.com/pricing

## Critical weaknesses

1. Evidence traceability is still too weak.
   The Evidence Pack stores sources, but the later draft and QC layers do not yet visibly tie claims back to specific evidence items.

2. Multi-user trust is not ready.
   There are no real roles, sessions, or enforcement boundaries yet.

3. Competitor ingestion is too light.
   It is useful as a signal layer but still partly curated and not robust enough to support strong commercial claims.

4. Storage is MVP-grade.
   File-backed storage is fast for demos but weak for concurrency, backup guarantees, and audit trust.

5. Control coverage is still partial.
   The new control panel and stale-artifact warnings help, but deeper governance such as enforced dependency invalidation after manual edits and source-level claim linkage are still missing.

## Missing controls and governance

Important missing or incomplete controls:

1. Citation-aware downstream control
   Later artifacts should know which source backs which claim.

2. Dependency invalidation control
   Basic stale warnings now exist, but approved downstream artifacts are not automatically invalidated when upstream inputs change materially.

3. Role and permission control
   Approval should be role-aware, not just button-based.

4. Audit log control
   Who changed what and why should be explicit beyond version snapshots.

5. Source freshness control
   Present but still basic; should affect step readiness and warnings more directly.

6. Model cost control
   No budgeting or token-usage tracking exists yet.

7. Approval integrity control
   Re-approvals and approval expiration rules are not defined.

## Vulnerabilities and failure modes

High-value failure modes:

1. Silent factual drift
   Human edits can change meaning without preserving source linkage.

2. False confidence in topic radar
   If competitor signals are weak or feeds are noisy, users may over-trust the scoring.

3. State ambiguity
   Basic stale warnings exist, but downstream steps can still look usable even when upstream inputs changed materially.

4. Concurrency risk
   File-backed storage is vulnerable to race conditions if multiple users interact at once.

5. Commercial overclaim risk
   The product can support topic prioritization, but should not imply guaranteed virality or guaranteed views.

## Sellability assessment

Current state:

- ready for pilot sales
- not ready for broad self-serve sale

Why:

- workflow is real
- value proposition is real
- topic radar is meaningfully differentiated
- but enterprise trust, governance, and collaboration are not yet strong enough

Best sales motion now:

- design partner
- founder-led sales
- channel/studio pilot

Not yet ideal for:

- high-volume inbound self-serve
- larger media organizations

## Recommended pricing logic

Position it above generic creator SEO tools and below enterprise media-intelligence platforms.

Suggested bands:

- Starter pilot: $79-$149 / month
- Pro team: $299-$499 / month
- Studio / agency: $900+ / month or custom

Why this range:

- vidIQ is priced like creator tooling, not editorial operations
- Exploding Topics sells trend intelligence
- BuzzSumo prices higher because it is a broader intelligence platform

Ike should price on saved editorial labor and improved hit-rate, not on "AI writing" alone.

## Priority roadmap

### Product

1. Add source-to-claim citation mapping
2. Enforce downstream stale-artifact invalidation
3. Add stronger competitor ingestion
4. Add export package for host recording
5. Add reusable project templates by channel format

### Controls

1. Role-based approvals
2. Explicit audit log
3. Source freshness gating
4. Approval invalidation after upstream changes
5. AI cost / usage controls

### Technical

1. Replace file storage with Postgres
2. Add auth
3. Add background job execution for long-running AI steps
4. Add regression smoke + browser E2E
5. Add observability around failed runs

## Sources

- YouTube Help: CTR, impressions, and packaging context
  https://support.google.com/youtube/answer/16767369?hl=en

- YouTube Help: audience retention and key moments
  https://support.google.com/youtube/answer/9314415?hl=en

- YouTube Help: new, casual, and regular viewers for content planning
  https://support.google.com/youtube/answer/10246996?hl=en

- vidIQ pricing and plans
  https://vidiq.com/plans/

- Exploding Topics pricing
  https://explodingtopics.com/pricing

- BuzzSumo pricing
  https://buzzsumo.com/pricing/

- TubeBuddy pricing
  https://www.tubebuddy.com/pricing
