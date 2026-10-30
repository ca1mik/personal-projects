# Deep Research Prompt

Use this prompt when you need a full strategic and product-ops audit of a workflow product like Ike.

## Prompt

You are a principal product strategist, staff security reviewer, workflow systems architect, and B2B SaaS operator.

Your task is to perform a full-stack research and audit review of the following product:

- Product name: `Ike Editorial Pipeline`
- Product type: human-in-the-loop editorial workflow tool for YouTube scripting on macroeconomic and economic-political topics
- Core behavior: upstream topic discovery + research aggregation + multi-step artifact pipeline + approvals + versioning

You must evaluate the product from six perspectives:

1. Market need
2. Target user and buyer
3. Product competitiveness
4. Workflow completeness
5. Vulnerabilities and control gaps
6. Monetization and sellability

## Goals

Produce an honest, critical report that answers:

- Why does this product need to exist in the market?
- Who specifically would pay for it?
- What adjacent tools already solve part of this problem?
- What important controls, review layers, or governance mechanisms are missing?
- What makes the product hard to trust, hard to adopt, or hard to pay for?
- What are the top product, UX, technical, operational, and commercial risks?
- What should be improved immediately to make it more competitive and more sellable?

## Required research method

- Use current sources, not memory.
- Prefer primary and official sources when evaluating competitors, pricing, platform behavior, or product claims.
- Distinguish clearly between:
  - verified facts
  - inference
  - recommendation
- Be skeptical and explicit about uncertainty.
- If a feature appears weak, say so directly.

## Audit dimensions

### 1. Product and workflow audit

Evaluate:

- Is the workflow complete for a real editorial team?
- Are there hidden points where the workflow breaks?
- Are approvals and version controls sufficient?
- Are there missing artifacts or missing transitions?
- Is the product too dependent on ideal user behavior?
- Are there places where the user can accidentally make a bad decision without warnings?
- Are there missing operational controls such as:
  - source freshness
  - evidence traceability
  - approval audit trail
  - role permissions
  - stale artifact detection
  - invalid downstream dependency warnings
  - competitor signal confidence

### 2. Vulnerability and failure-mode audit

Look for:

- data integrity risks
- bad fallback behavior
- hallucination pathways
- broken approval logic
- missing validation
- weak error handling
- ambiguous state transitions
- accidental overwrites
- weak auditability
- security or trust gaps for multi-user usage
- hidden cost traps in AI usage

### 3. Market and competitor audit

Research current competitors and adjacent tools such as:

- YouTube growth tools
- trend discovery tools
- media monitoring / content intelligence tools
- AI script generation products
- competitor tracking tools

For each category, answer:

- what they do well
- what they do not solve
- where this product is differentiated
- where this product is weak
- what pricing band the market suggests

### 4. ICP and buyer audit

Identify:

- end user
- economic buyer
- team structure
- pains severe enough to pay for
- expected budget range
- adoption blockers

### 5. Sellability audit

Evaluate:

- Can this be sold as self-serve now?
- Is it only ready for design-partner pilots?
- What proof is missing before a team would trust it?
- What must exist before charging meaningful money?

### 6. Prioritized recommendations

Return:

- top 5 product improvements
- top 5 control improvements
- top 5 technical improvements
- top 3 commercial improvements

## Output format

Return the report in this exact structure:

1. Executive summary
2. Why this product should exist
3. Who it is for
4. Current market comparison
5. Critical weaknesses
6. Missing controls and governance
7. Vulnerabilities and failure modes
8. Sellability assessment
9. Recommended pricing logic
10. Priority roadmap
11. Sources

## Tone

- blunt
- precise
- operator-level
- no marketing fluff
- no generic startup advice

If the product is not yet strong enough to sell broadly, say so clearly and explain why.
