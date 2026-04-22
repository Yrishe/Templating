# Support Software & Automation Research

**Prepared for:** Yarli
**Date:** April 21, 2026
**Context:** B2C customer support, mid-size team (10–50 agents), budget-aware but willing to pay for good UX, prefers fully managed services.

---

## TL;DR — Recommendations for your context

| Decision | Recommendation | Why |
|---|---|---|
| Support platform | **Chatwoot Cloud (Business plan)** as primary pick; **Intercom** if AI deflection is a top priority and budget can flex | Chatwoot is the best fit for B2C, multi-channel (email, chat, WhatsApp, social), mid-size teams that want predictable per-agent pricing without the Intercom tax. Plain is ruled out — it's explicitly B2B-focused. |
| n8n hosting | **n8n Cloud (Pro plan, ~€60/mo)** | You said "prefer fully managed." Self-hosting is cheaper on paper, but if you have no ops bandwidth the TCO flips against you. Only revisit self-host if you hit execution volume where Cloud gets expensive or you need data residency. |

The rest of this document walks through the reasoning.

---

## Part 1 — Chatwoot vs. Plain vs. Intercom

### Quick comparison

| Dimension | Chatwoot | Plain | Intercom |
|---|---|---|---|
| **Target market** | B2C & B2B, SMB to mid-market | **B2B only** (startups, dev-tools, API companies) | B2C & B2B, SMB to enterprise |
| **Pricing model** | Per agent/month (Cloud) or free self-hosted | Per user/month, caps on lower plans | Per seat/month **+ $0.99 per Fin AI resolution** |
| **Starting price (Cloud)** | ~$19–$99/agent/mo | $39/user/mo (Launch, cap 5 seats) | $29–$39/seat/mo (Essential) |
| **Realistic mid-tier price** | Business plan, ~$49/agent/mo | Grow ~$89/user/mo (cap 10 seats) | Advanced $99/seat/mo + Fin |
| **Channels** | Email, live chat, WhatsApp, FB, IG, Twitter, SMS, Line, Telegram, API | Email, Slack, Teams, Discord, portal, chat, API — **no social/WhatsApp native** | Email, chat, WhatsApp, SMS, social, phone |
| **AI features** | Captain AI (reply suggestions, summarization, KB answers) — credits included per plan | Ari (resolving agent) + Sidekick, included in every plan | Fin AI — industry-leading, but billed per resolution |
| **Self-host option** | ✅ Free (MIT) or paid premium | ❌ SaaS only | ❌ SaaS only |
| **Best for** | Budget-aware B2C multi-channel | B2B startups with technical users | Teams that value polish, AI deflection, and have budget |

### Chatwoot

Chatwoot is an open-source customer engagement platform that competes directly with Intercom on feature breadth at a fraction of the price. It supports the full channel matrix a B2C operation needs — email, website chat, WhatsApp Business, Instagram DMs, Facebook Messenger, SMS, Telegram, Line — under a unified inbox.

**Cloud pricing (2026):** Four tiers billed per agent/month. Every paid plan includes monthly Captain AI credits (300 for Startups, 500 for Business, 800 for Enterprise), with extra credits at $20 per 1,000. Captain covers reply suggestions, conversation summarization, and knowledge-base answers.

**Self-hosted:** The Community Edition is free under MIT, but you own the maintenance burden — upgrades, Postgres, Redis, storage, outbound messaging fees (Twilio, Meta, etc.). Premium self-hosted runs $19–$99/agent/mo and unlocks Captain AI and SLAs.

**Strengths**
- Best-in-class channel coverage for B2C (especially WhatsApp, Instagram)
- Transparent, predictable pricing — no "per-resolution" billing surprises
- Open-source heritage means good data portability and an active community
- Cloud version removes the ops burden while keeping the pricing advantage

**Weaknesses**
- AI is capable but not as mature as Intercom's Fin
- Reporting and analytics are solid but less polished than Intercom
- Some advanced workflow features sit behind the Enterprise tier

**Why it fits your context:** You're B2C, mid-size, budget-aware, and want managed. Chatwoot Cloud on the Business plan hits all four with no ops overhead.

### Plain

Plain is an AI-first, API-first support platform built explicitly for **B2B companies with technical users** — think dev tools, infra APIs, data platforms. It's Slack-native, unifies channels like email, Slack, Teams, Discord, portal, and chat, and ships with Ari (an AI agent that resolves tickets end-to-end) on every plan.

**Pricing (2026):**
- Launch — $39/user/mo, **hard cap of 5 seats**
- Grow — $89/user/mo, **hard cap of 10 seats**
- Scale — custom pricing, removes caps

All plans include AI, API calls, and integrations with no hidden per-feature upcharges — a meaningful differentiator versus Intercom.

**Strengths**
- Modern, developer-friendly UX (arguably the nicest-feeling inbox in the category)
- AI included at all tiers with no per-resolution billing
- Excellent for teams where Slack is the primary customer channel
- Transparent pricing, no upsells

**Weaknesses — why it's a bad fit for you**
- **Explicitly B2B.** No native WhatsApp, Instagram, Facebook, or SMS support. For a B2C operation where end users live on social and WhatsApp, this is a dealbreaker.
- Seat caps push a 10–50 agent team straight into "Scale" (custom pricing), which erodes the transparent-pricing advantage at your size.
- The tool is optimized for low-volume, high-technical-depth tickets — not high-volume consumer support.

**Verdict:** Skip Plain unless your support workload shifts toward B2B/developer users.

### Intercom

Intercom is the incumbent premium option. It bundles a messenger, help center, ticketing, and the Fin AI agent into a single polished suite, and has the deepest AI deflection capability in the market.

**Pricing (2026):**
- Essential — $29/seat/mo (annual) or $39 (monthly)
- Advanced — $99/seat/mo (annual required)
- Expert — $139/seat/mo (annual required)
- **Fin AI — $0.99 per successful resolution**, on top of seat fees

Fin only charges when it closes a conversation without human handoff — so the per-resolution cost scales with deflection value, not raw volume.

**Strengths**
- Fin AI is measurably the most effective out-of-the-box support agent on the market
- The most polished end-user experience (messenger, help center, proactive messages)
- Mature reporting, automation, and enterprise features
- Rich ecosystem — almost every SaaS tool has a first-class Intercom integration

**Weaknesses**
- **The real price is seat + Fin.** A 20-agent team on Advanced plus 5,000 Fin resolutions/month runs ~$1,980 in seats + ~$4,950 in Fin = **~$6,930/month**. That's the pattern to model carefully before committing.
- Annual-required pricing on better tiers reduces flexibility
- Historically the platform most likely to surprise you at renewal

**When Intercom is the right call:** You have a business where (a) AI deflection directly offsets headcount — a single deflection saves more than $0.99 of agent time — and (b) you value the polish enough to pay the premium. For a well-funded mid-size B2C team where support volume is growing faster than you can hire, Intercom pays for itself.

### How to choose between them (for your profile)

The decision turns on a single question: **Is AI deflection a strategic must-have, or a nice-to-have?**

- If **must-have** — you're drowning in volume, hiring can't keep up, and you can model a real ROI on deflected tickets — Intercom is worth the premium. Budget for seats *and* Fin usage from day one.
- If **nice-to-have** — you have competent humans handling volume and want AI as an assist — Chatwoot Cloud (Business) gets you 80% of the capability at roughly a third of the total cost, with multi-channel coverage that matches or exceeds Intercom.

For a mid-size B2C team described as "budget-aware but willing to pay for good UX," Chatwoot is the stronger default and Intercom is the justified upgrade if you can show deflection ROI.

---

## Part 2 — n8n: Self-hosted vs. Cloud

### Pricing comparison (2026)

| | n8n Cloud | n8n Self-hosted |
|---|---|---|
| **Software cost** | Starter €24/mo (2,500 executions); Pro €60/mo (10,000); Business €800/mo (40,000) | Free (Community Edition, fair-code license) |
| **Infrastructure** | Included | ~€5–20/mo (VPS) to €50+ for HA setup |
| **Executions** | Capped by tier | Unlimited |
| **Active workflows** | Unlimited on every plan (April 2026 update) | Unlimited |
| **SSO / audit logs** | Business / Enterprise only | Enterprise license required |
| **Upgrades, backups, security patches** | Handled for you | Your problem |
| **Ops time per month** | ~0 hours | 2–8 hours typical |

### Self-hosted — when it makes sense

- You already run Docker/Kubernetes infrastructure and adding another service is marginal effort
- You have **data residency or compliance requirements** (GDPR, HIPAA, regulated industries) that require workflow data never leaves your environment
- Your execution volume is high enough that Cloud pricing becomes punitive (tens of thousands of executions/month)
- You want to fork or modify n8n itself

### Cloud — when it makes sense

- You want to focus on building workflows, not operating infrastructure
- Execution volume is predictable and moderate (< 10,000/mo fits comfortably in Pro)
- You want automatic upgrades, managed backups, built-in monitoring, and a support contract
- You don't have strict data-residency requirements

### Recommendation for your context

You explicitly said "prefer fully managed" with "no ops bandwidth." That's the entire answer.

**Start on n8n Cloud Pro (€60/mo).** Revisit self-hosting only if one of these becomes true:
1. You cross ~40,000 executions/month and Business-tier pricing becomes painful
2. A compliance or customer contract demands data never leaves your infra
3. You build enough n8n-centric internal tooling that a dedicated platform engineer makes sense

The "self-host saves €200–700/year" math sounds attractive until you spend one Saturday debugging why Postgres disk filled up. For a mid-size team without dedicated devops, Cloud's TCO wins.

---

## Decision framework — putting it together

For a typical mid-size B2C operation with no ops bandwidth, the clean stack is:

**Chatwoot Cloud (Business plan) + n8n Cloud (Pro plan)**

- Chatwoot handles multi-channel support with transparent pricing
- n8n Cloud handles automation (ticket routing, CRM sync, escalation workflows, Shopify/Stripe integrations)
- Neither requires an ops team
- Total baseline cost for a 20-agent team: roughly $980/mo (Chatwoot) + €60/mo (n8n) ≈ **$1,050/mo all-in before messaging fees**

Upgrade paths if needs change:
- Support volume explodes and AI deflection matters → swap Chatwoot for **Intercom + Fin**
- Workflow complexity or compliance grows → migrate n8n to **self-hosted** with a dedicated owner
- You pivot to B2B/dev-tool customers → reconsider **Plain**

---

## Sources

### Chatwoot
- [Self-Hosted Pricing | Chatwoot](https://www.chatwoot.com/pricing/self-hosted-plans/)
- [Pricing | Chatwoot](https://www.chatwoot.com/pricing/)
- [Chatwoot Pricing 2026: Is It Worth It?](https://www.featurebase.app/blog/chatwoot-pricing)
- [Chatwoot Review 2026: Pricing, Features, Pros & Cons](https://research.com/software/reviews/chatwoot)
- [Managing Enterprise Edition Features — Chatwoot Developer Docs](https://developers.chatwoot.com/self-hosted/enterprise-edition)

### Plain
- [Plain — The AI Support Stack Built for B2B](https://www.plain.com/)
- [Plain Product — AI Support Infrastructure for B2B Teams](https://www.plain.com/product)
- [Plain Pricing 2026](https://www.g2.com/products/plain/pricing)
- [Plain Pricing 2026: Is It Worth It?](https://www.featurebase.app/blog/plain-pricing)
- [15 Best Customer Support Software for B2B in 2026](https://www.plain.com/blog/customer-support-software)

### Intercom
- [Intercom Pricing | Plans for every team size](https://www.intercom.com/pricing)
- [Intercom Pricing 2026: Seat Fees + $0.99 Per AI Resolution Explained](https://intercompricing.com/)
- [Intercom Fin AI Agent Pricing in 2026: A Clear Breakdown](https://minami.ai/blog/intercom-fin-ai-agent-pricing)
- [Intercom Pricing 2026: Full Breakdown & Cheaper Alternatives](https://www.robylon.ai/blog/intercom-pricing-breakdown-2026)
- [Intercom Fin AI: Guide to Features, Pricing & Limitations (2026)](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026)

### n8n
- [n8n Plans and Pricing](https://n8n.io/pricing/)
- [n8n Pricing in 2026: Cloud vs Self-Hosted Costs Compared](https://instapods.com/blog/n8n-pricing/)
- [n8n Pricing 2026: Free Self-Hosted vs $24/mo Cloud](https://automationatlas.io/answers/n8n-pricing-self-hosted-vs-cloud-2026/)
- [n8n Self-Hosted vs n8n Cloud vs Zapier: The True Cost of Workflow Automation in 2026](https://massivegrid.com/blog/n8n-pricing-self-hosted-vs-cloud-vs-zapier/)
- [How to self-host n8n: Setup, architecture, and pricing guide (2026) — Northflank](https://northflank.com/blog/how-to-self-host-n8n-setup-architecture-and-pricing-guide)
