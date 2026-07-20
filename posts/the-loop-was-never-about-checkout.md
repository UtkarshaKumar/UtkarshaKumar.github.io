---
title: The Loop Was Never About Checkout
date: 2026-07-20
---

Most "AI agent for commerce" builds today are the same shape: an agent handles a support ticket, closing a loop — sense the request, take an action, check the result, repeat until resolved. It's a sound pattern. The question worth asking is where else that loop belongs, and 2026 has given a fairly precise answer already.

## Two loops, not one

Anthropic's own description of how their agents work is a useful starting point: an agent runs a loop of **gather context, take action, verify work, repeat** — a tight cycle scoped to a single task. Call this the inner loop. It's what happens inside one customer's session: understand what they're asking for, propose something, see how they respond, adjust.

But an inner loop on its own doesn't get better over time — it resolves the task in front of it and starts over from zero with the next one. What makes a system improve is a second loop wrapped around many inner loops: aggregate what happened across sessions, evaluate it against a goal, optimize whatever the inner loop draws on, publish the update. This is close to Anthropic's evaluator-optimizer pattern, just applied at the system level instead of within a single generation — a generator (the inner loop) produces outcomes, an evaluator scores them in aggregate, and the correction feeds back in. Call this the outer loop.

The diagram below is the argument in one picture:

![Inner loop, outer loop — applied to commerce discovery](img/inner-outer-loop-diagram.svg)

Every commerce surface that uses agents — support, checkout, discovery — runs both loops. The difference between them isn't whether they compound. It's where the outer loop's improvements land, and how much of the customer base they touch.

## Where each outer loop lands

A support loop's outer cycle improves how the next ticket gets handled — better macros, better routing, a model that's seen more edge cases. Real value, but it only ever touches customers who already converted and already ran into a problem. That's a narrow, late slice of the funnel.

A checkout loop's outer cycle improves conversion at the transaction — less friction, better-timed prompts, smarter fallback when a card fails. It only touches customers who have already decided to buy and reached the last step. Narrower still.

OpenAI's Instant Checkout is a live example of what happens when the loop is built at that layer. Launched in February on the Agentic Commerce Protocol it built with Stripe, it let ChatGPT users buy directly inside the chat. By [its own account six months later](https://www.cnbc.com/2026/03/24/openai-revamps-shopping-experience-in-chatgpt-after-instant-checkout.html), roughly 30 merchants were actually live on it, well short of what was originally described. Walmart measured checkout inside ChatGPT converting about three times worse than a click-through to walmart.com, even as ChatGPT sent them roughly twice the new-customer rate of search. OpenAI's stated response was to let merchants keep their own checkout experiences and shift its effort to product discovery instead.

A discovery loop's outer cycle improves ranking, matching, and merchandising — what gets surfaced at all. It runs for every visitor, before purchase intent has hardened into a decision, which means its outer loop has the widest population to learn from and the earliest point in the funnel to act on. Google's Universal Commerce Protocol, which Gap adopted in March for [agentic checkout inside Gemini](https://www.cnbc.com/2026/03/24/gap-google-gemini-checkout-ai-platform.html), makes the ordering explicit: product data is a feed the retailer submits in advance, and a product that isn't surfaced in the AI conversation can't be purchased through it at all. The protocol enables the transaction; it doesn't guarantee the recommendation. Discovery decides what checkout ever gets a chance to close.

## What the outer loop actually runs on

The outer loop's optimize step is only as good as what it's optimizing over — structured, machine-readable product data: attributes, use-case descriptions, real-time price and inventory. That's the layer I've spent twelve years in: B2B catalogs, complex contract pricing, account hierarchies — the plumbing that determines whether an agent can reason about a catalog or is guessing from a stale title.

This is the part most loop pitches skip. An inner loop acting on bad catalog data doesn't improve with repetition — it gets confidently wrong, faster. The outer loop compounds on data quality before it compounds on anything else. Get the feed wrong and the result isn't a discovery loop; it's a fast way to recommend the wrong thing to more people.

## Where this points

Support and checkout loops are worth having — they're just narrow, late, and downstream. The discovery loop is the one with the earliest, widest outer cycle: it touches every customer, not the unhappy or the already-decided ones, and its output changes what the next customer even sees. If I were prioritizing a year of agent-loop investment in commerce, it's there — and in the catalog and pricing infrastructure the outer loop depends on to be right in the first place.

---

*Sources: [OpenAI's Instant Checkout pivot, CNBC](https://www.cnbc.com/2026/03/24/openai-revamps-shopping-experience-in-chatgpt-after-instant-checkout.html) · [Gap's Google Gemini checkout launch, CNBC](https://www.cnbc.com/2026/03/24/gap-google-gemini-checkout-ai-platform.html) · [Buy It in ChatGPT, OpenAI](https://openai.com/index/buy-it-in-chatgpt/) · [Building Effective Agents, Anthropic](https://www.anthropic.com/research/building-effective-agents) · [Effective Harnesses for Long-Running Agents, Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)*
