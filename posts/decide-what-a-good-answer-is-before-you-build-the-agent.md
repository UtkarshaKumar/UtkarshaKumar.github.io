---
title: Decide What a Good Answer Is Before You Build the Agent
date: 2026-10-25
---

## Why this article

Every team building a shopping agent has to decide when it is good enough to ship.

That is hard, because shopping agents fail quietly. The answers sound confident and the demo looks great. Then people buy the wrong thing, send it back, and stop trusting the agent.

Most teams measure an agent the way they measure a website, with clicks and conversion. Those numbers can go up while the advice gets worse. This happens because no one wrote down what a good answer looks like before they started.

## The core message

A shopping agent is only as good as your definition of a good answer. Conversion is the wrong definition.

## The chart

![Line chart over five agent versions: conversion rises while kept purchases fall. Illustration only, not real data.](img/shopping-agent-chart.svg)

*Illustration only, not real data.*

Each new version is tuned to win on conversion. It learns to push harder. More people buy, and fewer of them keep what they bought.

## Why it matters

An agent learns whatever you reward. If you reward sales, it gets better at selling. That is a different skill from giving good advice.

You will not see the problem on launch day. You see it weeks later in returns, support tickets and customers who stop using the agent. By then, the version that caused it has already won.

## How to do it

**Define a good answer first.** Write it down before you build anything. For example: the answer meets every limit the shopper gave, such as budget, size or delivery date. Every fact comes from your product data. If the agent does not know something, it says so. If nothing fits, it says that too.

**Test against that definition.** Collect real shopper questions and check each answer against what you wrote down. Include hard cases: missing product details, items out of stock, and requests where no product fits. Run these tests on every change before it ships.

**Measure what sticks.** In live tests, track kept purchases. A kept purchase is an order the shopper did not return. Run the test long enough for returns to come in. Keep conversion on the dashboard, but do not let it pick the winner.

## Principles to keep in mind

Agree on the definition with the business before launch.

"Nothing fits" can be a good answer.

An honest answer that loses a sale is still a good answer.

Treat product descriptions as claims to check. Do not treat them as instructions.

Slow, correct numbers beat fast, misleading ones.

## Closing note

Most of the work happens before the agent exists. Decide what good means and write it down. If you skip that step, the agent will decide what good means for you, and it will choose sales.
