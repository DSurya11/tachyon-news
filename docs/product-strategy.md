# From pipeline to Play Store: how to make this app different

*Written 29 Sep 2026. Based on this repo, the local database as of 28 Sep, and web research (sources at the end).
Statements marked **(estimate)** are my judgement, not sourced facts. Nothing here is legal advice. Get a
securities lawyer to review section 6.2 before you launch.*

---

## 0. Summary

**What you have:** a solid news-intelligence engine. It scrapes about 330 stories a day across the US and
India, uses an LLM to pull out tickers, events, sentiment and numbers, and then **checks the LLM's quote and
numbers against the article text**. It also writes a cited daily brief. About 85% of extractions pass that
check. Very few consumer apps do this kind of source checking.

**What you don't have yet:** a product people can't get elsewhere, or the legal right to ship it.
"AI summary + bullish/bearish tag" is already free in 2026 (StockFlash, Aktai, Tickertape, Perplexity
Finance, Zerodha Pulse). If you ship the current feature set as an Android app, it will look like a
copy of all of them.

**The positioning I recommend:**

> **The market-news app that shows its receipts.** It tells you what happened, whether it's true,
> whether it's already in the price, and whether it touches *your* money. It also keeps a public record of
> how often it was right.

The four features competitors don't have. Each builds on something this repo already does:

1. **Receipts**: a public, automatic scorecard of the app's own accuracy (section 3.1).
2. **Priced-in meter**: "this stock already moved 4% on this news; news like this usually fades or keeps
   going" (3.2).
3. **Overnight Bridge**: US news from last night, mapped to the Indian stocks it will hit at 9:15 AM IST.
   You already cover both markets and both currencies (3.3).
4. **Tip Checker**: forward a WhatsApp or Telegram stock tip and get a risk check back. This is the
   growth loop (3.5).

**What blocks a launch today** (section 6):

1. The data sources (Finviz scraping, yfinance, free-tier LLMs, automating the Claude.ai website) are
   personal-use only. You cannot ship them commercially. **This is a hard blocker.**
2. Under SEBI rules, bullish/bearish labels and "top picks" on named Indian stocks sit in a grey zone. You
   need to decide: stay a news platform, or register as a Research Analyst.
3. The pipeline runs hourly from your laptop. Alerts need about 1 minute, not up to 60.
4. There is no mobile basics layer yet: push notifications, widgets, offline cache, account deletion,
   Play policy forms.
5. There is no history yet: 3 days of data. Every model in section 4 needs months of stored events and
   price outcomes. **Start storing them this week**, even before the app exists.

---

## 1. Where the project stands today (honest audit)

### What's genuinely strong

| Asset | Why it matters for a product |
|---|---|
| **Verifier** (evidence quote + every number checked against the article) | This is your trust story. Most AI news apps can't prove their summaries match the source. |
| **Two markets in one pipeline** (Finviz US + Indian RSS), USD↔INR conversion | This supports the cross-market angle (3.3). Indian apps are India-only, and US apps ignore India. |
| **Noise tagging** (law-firm ads, dividend notices, Nasdaq letters) | "Signal, not noise" is a brand, not just a filter. |
| **Cited daily brief + "top picks" with a one-line reason** | The start of an editorial voice. |
| **Bodies, evidence and key facts never leave the laptop** | You already avoid republishing copyrighted text. Keep this rule. |
| **Symbol checks** (hides LLM-invented tickers) | Proof you've already hit the entity-linking problem (4.1). |
| **Tests + CI, clean API, polished dashboard** | You can move fast without breaking things. |

### What an investor would flag (numbers from the local DB, 28 Sep 2026)

| Finding | Number | Why it matters |
|---|---|---|
| History | ~1,090 articles, **Sep 25 → Sep 28** | Too little history to train or back-test anything. |
| Users | 2 accounts, 2 reports | No usage data yet. |
| Verified rate | 835 of 986 extractions (**~85%**) | A good number. Publish it (3.1). |
| **Press-release share** | **24%** of all articles come from paid wires (GlobeNewswire, PR Newswire, Business Wire, ACCESSWIRE) | A quarter of the feed is company-written marketing. |
| **Press-release bias** | Press wires: 47% bullish / 10% bearish (**4.6 : 1**). Editorial: 36% / 29% (**1.25 : 1**) | Your sentiment totals are pushed upward by paid releases. This is a feature opportunity (3.6). |
| India coverage | 163 extracted India stories; 108 with tickers; Indian tickers live only in `extractions`, not `article_tickers` | India is ~16% of volume, but India is where your users will be. |
| India ticker quality | LLM output includes symbols that must be checked against the NSE/BSE master (hence `symbol_checks`) | Wrong ticker = wrong alert = uninstall. |
| Extraction models | `ministral-8b` (593), `gemini-flash-lite` (386), through free OmniRoute combos | Free tiers have no uptime guarantee and often forbid commercial use. Output quality varies by model. |
| Timestamps | `published_at` = scrape time − Finviz age string (older rows are day-level, e.g. "Sep-18") | A priced-in or reaction model needs minute-level timestamps. |
| Latency | Hourly cron | Fine for a daily brief. Fatal for alerts. |
| Unused schema | `story_clusters`, `sector_day_features` defined but empty | Planned intelligence that doesn't exist yet. |

---

## 2. The market in 2026: who you're up against

| App | What they do well | What's missing (your opening) |
|---|---|---|
| **Zerodha Pulse** | Free, simple aggregator of major Indian financial news; Zerodha's reach | No AI, no checking, no personalization, no "so what" |
| **Tickertape** | Screener (200+ filters, ~4,600 Indian stocks), Market Mood Index, AI sentiment, portfolio import from 16+ brokers | Sentiment is just a label. No reaction or priced-in view, no source audit. |
| **StockFlash** | 50–60 word summaries, positive/negative sentiment, AI chat, India + global | Exactly the "summary + sentiment" template |
| **Aktai** | Per-ticker positive/negative alerts with a plain-English "why", 30+ exchanges, sector mood, no ads; also sells tools to SEBI-registered analysts | **Closest competitor.** I found no public accuracy scorecard, no priced-in view, no cross-market mapping. |
| **Perplexity Finance** | Live data + LLM, earnings hub, plain-English screener, portfolio via Plaid, covers Indian equities. $20 / $200 per month | A general answer engine: you have to ask. No curated, checked feed; shallow on Indian filings; no track record. |
| **Groww / brokers** | Huge reach, trading built in | They earn when you trade (conflict of interest). News is a side feature. |
| **Trendlyne / StockEdge / Ticker (Finology)** | Screeners, scans, data, concall links | Research tools, not news intelligence |

**What this means:**

- **These are table stakes, not differentiators:** summaries, sentiment tags, AI chat, a watchlist,
  sector mood, price alerts.
- **Nobody combines all of these:** (a) proves its accuracy publicly, (b) measures whether news is already
  priced in, (c) connects US news to Indian holdings, (d) protects users from tip scams.

**The real market size.** India has **237.7M demat accounts** (Aug 2026) and **26 crore NSE unique client
codes** (Jun 2026). But only about **1.08 crore investors were active in the cash market** in May 2026.
Your realistic target is the ~1 crore people who actually invest, not 23 crore accounts. Pitch the smaller,
real number to investors; they will check it.

**The problem you're solving.** SEBI found **91% of individual F&O traders lost money in FY25**
(net losses of ₹1.06 lakh crore). SEBI is also cracking down on social-media pump-and-dump groups
(interim order in May 2026 over X, Telegram and WhatsApp stock-tip networks). Most apps push people to
trade *more*. A calm app that says "this is noise for you, do nothing" and "this tip looks like a
pump-and-dump" suits both users and the regulator.

---

## 3. Signature features: what makes it "never seen before"

Each feature lists: what the user sees → why it's new → what it needs → watch-outs.

### 3.1 Receipts: the app grades itself in public ★ core differentiator

**What the user sees:** a "Track record" screen, and a small badge on every card:
- *Extraction accuracy:* "92% of our summaries passed source checks this week" (your verifier already
  produces this).
- *Reaction calibration:* "When we said a story would probably fade, it faded 64% of the time (last 90 days,
  1,240 stories)."
- *Per-source record:* "Rumors from Source X were confirmed within 30 days 38% of the time."
- Every past label stays visible with its timestamp. Nothing is silently edited or deleted.

**Why it's new:** AI finance apps ask for trust but never measure themselves. A public, unedited
scorecard is hard to copy quickly, because it needs months of your own logged history.

**What it needs:** version every extraction instead of overwriting (see 4.0), plus an outcomes table and a
nightly scoring job.

**Watch-outs:** SEBI now requires registered advisers and analysts to have past-performance claims verified
through **PaRRVA** (live since May 2026). Score **information quality** (was the summary right, did the
reaction match the historical range), **not "returns if you followed us"**. If you register as a Research
Analyst later, any performance claim must go through PaRRVA.

### 3.2 Priced-in meter ★ core differentiator

**What the user sees** on a story card:
> "INFY is already **−4.1%** since this headline. Similar news (earnings guidance cut, large-cap IT)
> historically moved stocks **−6% to −1%** by day 5 (median −2.8%). **Mostly priced in.**"

**Why it's new:** Apps tell you whether news is good or bad. None tell you whether it's too late to matter.

**Research backing:** An Aug 2026 study of **4.57M articles on ~3,000 US stocks (2023–26)** found that the
move by the close of the publication day is **2.8× what's left 20 days later**. In other words, most of
the first-day move fades. It also found that **hard-number news (earnings, dividends) keeps drifting for
weeks, while story-driven news (launches, commentary) tends to reverse.** Lopez-Lira & Tang also found
that LLM news scores predict the first reaction and the later drift, most strongly for smaller stocks and
negative news. That's a rule you can use from day one, before any model exists.

**What it needs:** exact publication timestamps, intraday prices (at least 15-minute bars), an index or
sector benchmark, and the reaction model (4.4). **Version 1 can be pure statistics:** event type ×
market-cap bucket × first-report flag → historical range. No deep learning required.

**Watch-outs:** Show it as history ("news like this historically…"), never as a forecast or instruction.
No "buy" or "sell" wording.

### 3.3 Overnight Bridge: US news → Indian stocks at 9:15 AM ★ uses your unique dual-market setup

**What the user sees:** a 7:30 AM IST card: *"3 things from last night that touch your Indian holdings."*
Examples of the links:
- Accenture results or US tech spending news → TCS, Infosys, Wipro, HCLTech
- US FDA warnings or approvals → Sun Pharma, Dr. Reddy's, Cipla, Lupin
- Crude oil moves → oil marketing companies, paint makers, airlines
- Fed decisions → FPI flows, banks, INR
- **Indian ADRs traded overnight in the US** (INFY, WIT, HDB, IBN, RDY) → a real pre-open signal for the
  same companies in India

**Why it's new:** Indian apps are India-first, and US apps ignore India. You already scrape both, store both
currencies, and write a daily brief. This connects them.

**What it needs:** a US↔India link graph (4.9). Start with a hand-built table of about 200 links (ADR
pairs, sector peers, known big customers), then let the LLM propose new links from filings.
Also: the brief must be written **before 8 AM IST**, which is after the US close. Your trading-day logic
already handles the 4 PM ET cutoff.

### 3.4 My Exposure: news that touches your money, including your mutual funds

**What the user sees:** import holdings once. The feed then answers "does this affect me?", including
**through mutual funds**:
> "HDFC Bank news → you hold it directly (₹42k) **and** through 3 funds (₹18k look-through). Total
> exposure: 6.1% of portfolio."

**Why it's new:** Portfolio news matching exists. **Matching news through mutual fund holdings** is rare,
and Indian retail investors hold much of their equity through mutual funds (estimate). SEBI requires funds
to publish monthly portfolio disclosures, so the data is public.

**How to import holdings, from easiest to hardest:**

| Route | Effort | Notes |
|---|---|---|
| **CAS PDF upload** (NSDL/CDSL consolidated statement) | Days | No licence needed. User uploads, you parse. Parser APIs exist (e.g. CASParser). |
| Broker login APIs (e.g. Kite Connect, Upstox) | Weeks | User consent. Check each broker's commercial terms. |
| Account Aggregator (NSDL/CDSL are live data providers) | 5–10 months, ₹5–25 lakh+, **must be a regulated entity** | Later, once you're funded. |

**Watch-outs:** holdings are sensitive personal data under the DPDP rules (6.5). Offer a "portfolio stays
on my phone" mode: match news on the device, never upload holdings. That's also a trust feature you can
advertise.

### 3.5 Tip Checker: forward a tip, get a risk check ★ the growth loop

**What the user sees:** share a WhatsApp or Telegram tip ("XYZ multibagger, target ₹500, record breaking
results coming!!") into the app. It replies with a shareable card:
> **High risk.** SME stock · price +180% in 30 days on 6× normal volume · no exchange filing supports the
> claim · on the exchange's watch list (ASM stage 2) · wording matches known pump-and-dump messages · the
> sender is not a SEBI-registered analyst.

**Why it's new:** No investing app does this, and it's exactly the problem SEBI is fighting (May 2026
interim order: X + Telegram + WhatsApp networks pumping SME stocks with "record breaking" and "multibagger"
posts). It is **investor protection, not advice**, which puts you on the regulator's side.

**Why it drives growth:** people forward the result back to the group ("checked it, it's a pump"). Every
check advertises the app inside WhatsApp groups, which is where Indian investors actually talk.

**What it needs:** the risk classifier (4.7); the exchange's public ASM/GSM surveillance lists; SEBI's
registered-intermediary lookup; price and volume data; your news and filings coverage.

### 3.6 Source honesty labels

**What the user sees:** a small label on every card: `Paid press release`, `Company filing`, `Journalism`,
`Opinion`, `Rumor (unconfirmed)`. Plus a per-source record (from 3.1). The sector-mood gauge counts press
releases separately.

**Why:** your own data shows paid releases are 24% of the feed and skew 4.6:1 bullish. Showing this is
honest, and no one else does. It also fixes your sentiment numbers.

**What it needs:** a source-type table (almost free: wire domains are known) + the source reliability model (4.6).

### 3.7 Calm mode: "Does this matter to me?"

**What the user sees:** each story gets one of three verdicts for *this user*: **Act-worthy / Worth
knowing / Noise for you**. There is a daily push budget (default: max 3). Weekend digest instead of
weekend pings.

**Why:** the #1 reason news apps get uninstalled is too many notifications (estimate, from general
mobile-retention experience). It's also your brand: *the app that makes you trade less, but better*. That
contrasts with broker apps that profit from activity, and matches SEBI's concern about F&O losses.

**What it needs:** the relevance and notification-budget model (4.8). It can start as rules:
holding × materiality × novelty.

### 3.8 Filings first for India

Company filings (NSE/BSE announcements: results, board meetings, orders won, pledges, insider trades,
bulk and block deals) come out **before** the press writes about them, and they are the primary source.
Summarize each filing with the same verifier. Add **concall summaries** where every number is checked
against the transcript. Source label: `Company filing`.

Check NSE/BSE terms for automated access and display before building this (6.1).

### 3.9 Checked regional languages (text + audio)

Hindi, Telugu, Tamil, Marathi, Bengali summaries, plus a **2-minute audio brief** at 8 AM. Tier-2 and
tier-3 cities drive new demat growth, and English excludes most of those users.

**The part only you can do:** run the verifier on translations too. Every number in the Hindi summary must
match the English source. "Numbers-checked Hindi news" is a claim no one else can make.

**Build vs buy:** buy translation and speech (Indic LLMs or translation APIs). Build the finance glossary
and the number checker.

### 3.10 Story timelines

Group articles about the same event (fills your empty `story_clusters` table). Show "first reported by X
at 09:42, 14 follow-ups, nothing new since 11:00". This cuts duplicate alerts and powers "first report"
features in 3.2 and 3.1.

---

## 4. The intelligence stack: which models to build

### 4.0 Before any model: start the dataset clock now

**Your moat is not a model. It's the dataset:** every news event, with a checked extraction, an exact
timestamp, and what the price did afterwards. Models trained on it can be rebuilt; the history cannot. Every
week you don't log is history you can never get back.

Concrete schema changes for this repo:

| Change | Why |
|---|---|
| `extraction_versions` (article_id, model, prompt_version, output, verified, created_at). **Never overwrite.** | `extractions` is one row per article today, so re-extraction destroys history. Models need point-in-time labels. |
| Exact `published_at` from the source (RSS `pubDate`, article meta, API) | Age strings are coarse; reaction models need minutes. |
| `prices_intraday` (15-minute or 5-minute bars, from a licensed feed) | Daily closes can't answer "has it moved since the headline?" |
| `event_outcomes` (cluster_id, ticker, t0 price, returns at +1h/close/+1d/+5d/+20d, benchmark return, abnormal return, volume ratio) | This is the label for 3.1, 3.2, 4.4 and 4.6. |
| Fill `story_clusters` and `sector_day_features` | Already planned in the schema. |
| `user_feedback` (opened, dismissed, muted, "not relevant"), with consent | Label for 4.8. |

### 4.1 Models, in build order

| # | Model | What it does | Type | Training data | When it's feasible |
|---|---|---|---|---|---|
| 4.1 | **Ticker linker** | Text → correct NSE/BSE/US symbol, including aliases ("RIL", "Reliance Inds") | Small fine-tuned encoder (ModernBERT / DeBERTa-v3) + lookup against the official symbol lists | Your LLM tickers that passed `symbol_checks` and the verifier + ~500 hand-labelled articles | **Now** (weeks) |
| 4.2 | **Distilled classifier** (event type, tone, materiality, source type) | Replaces most LLM calls: fast, cheap, stable | Student model trained on LLM outputs (distillation). Multilingual base (e.g. MuRIL/IndicBERT) for Hindi news | Your extraction history | After ~20–50k extractions **(estimate)** |
| 4.3 | **Story clustering + novelty** | Same-event grouping, first-report flag, "is this new?" | Multilingual sentence embeddings (e.g. bge-m3) + online clustering | Self-supervised; tune on ~300 labelled pairs | **Now** |
| 4.4 | **Reaction model** ★ proprietary | Predicts the *range* of abnormal return and volume at +close/+1d/+5d/+20d from event features | v1: grouped statistics. v2: LightGBM quantile regression. v3: sequence transformer over a stock's news history. Conformal prediction for honest ranges. | `event_outcomes` | v1 after ~3 months; v2 after ~6–12 months **(estimate)** |
| 4.5 | **Surprise extractor** | "Revenue ₹X vs ₹Y last quarter / vs own guidance" | LLM extraction + your number verifier + stored history | Your own past extractions (consensus estimates need a paid licence) | After ~2 quarters of history |
| 4.6 | **Source reliability** | Per source × event type: rumor confirmation rate, bullish bias, retraction rate | Bayesian counting (beta-binomial), not deep learning | `event_outcomes` + clusters | ~3 months |
| 4.7 | **Tip-risk scorer** | Pump-and-dump likelihood for a forwarded message + stock | Text classifier (promotional language) + anomaly detector (isolation forest on volume z-score, run-up, free float, SME board, ASM/GSM status) | **SEBI's published orders name manipulated stocks and dates: free labelled examples.** Plus your own tagged tips. | v1 as rules immediately; model after ~6 months |
| 4.8 | **Relevance + push budget** | Ranks the feed per user; decides which items earn a notification | LightGBM LambdaRank, then a bandit for push timing | `user_feedback` | After a few thousand active users |
| 4.9 | **Exposure graph** | Company ↔ supplier, customer, peer, ADR, fund holdings, commodity, currency | Graph built with LLM extraction from filings and annual reports. Later a graph neural net for shock propagation. | Filings, MF disclosures, hand-built seed table | Seed table now; GNN in year 2 |

### 4.2 The flywheel

```
  news + filings ──► checked extraction ──► story cluster ──► outcome logged (price moved how?)
        ▲                                                          │
        │                                                          ▼
  more users, more              public Receipts page ◄── models improve (4.4, 4.6, 4.7)
  holdings & feedback ◄── trust ◄──────────┘                       │
        │                                                          ▼
        └──────────────► relevance model (4.8) ──► fewer, better alerts ──► retention
```

### 4.3 What NOT to build

- **Your own foundation LLM.** Rent it. Your edge is the checking layer and the outcome data.
- **Buy/sell signals, target prices, "stock of the day".** That is research under SEBI rules (6.2), and it
  kills trust the first time it's wrong.
- **A chatbot as the headline feature.** Perplexity and others do this better. A grounded "ask about
  my holdings" answered only from your checked data is fine as a *supporting* feature.
- **On-device LLM summaries as a core feature.** Gemini Nano's summarization API supports English,
  Japanese and Korean only (no Indic languages yet), and only on recent chips. Use it as an optional
  privacy extra at most.

### 4.4 Model hygiene (where finance ML usually fails)

- **Look-ahead bias.** Only use information available at the headline's timestamp. LLMs trained *after*
  an event can leak future knowledge into labels. There's 2025–26 research on detecting exactly this.
  Train and evaluate on data after the LLM's training cutoff.
- **Signals decay.** Re-check the reaction model monthly. If calibration drifts, the Receipts page shows it,
  which is the point.
- **Survivorship.** Keep delisted and suspended symbols in history.

---

## 5. Target user and the pitch

**Primary user:** an Indian retail investor, 25–40, tier-1/tier-2 city, holds 5–30 stocks plus mutual
funds, and increasingly some US stocks. Not an F&O day trader. Reads news on the phone in the morning and
at lunch. Is flooded with tips on WhatsApp and Telegram.

**One-line pitch:** *"Checked market news that tells you whether it's true, whether it's priced in, and
whether it touches your money, with a public record of how often we're right."*

**Why now:** a boom in retail investors, SEBI's crackdown on finfluencers and pump-and-dump groups, cheap
LLMs making summaries free (so trust is what's scarce), and the rise of LRS/US investing from India.

---

## 6. What's missing: the investor checklist

Severity: 🔴 blocks launch · 🟠 needed before public launch · 🟡 needed before fundraising

### 6.1 🔴 Legal right to the data

| Today | Problem | Replace with |
|---|---|---|
| Finviz scraping | Finviz terms prohibit reselling scraped data; the README says personal use only | A licensed news API (e.g. Benzinga, Finnhub commercial, Marketaux: compare **redistribution** terms, which are usually a separate contract) + primary sources (SEC EDGAR, exchange filings) |
| yfinance (prices) | Yahoo data is personal use; unofficial endpoints | A licensed vendor. For India, exchange data needs an NSE licence, direct or via a licensed redistributor (e.g. TrueData). Delayed or end-of-day data is cheaper. Or show no price at all and link to the user's broker. |
| Publisher RSS + article bodies | Fine for processing; **republishing** bodies is not | Keep today's rule: store bodies privately, show only your own summary + a link. Get a lawyer's opinion on fair dealing under Indian copyright law. |
| Free-tier LLM combos via OmniRoute | Free tiers usually forbid commercial use, and have no uptime guarantee | One or two paid APIs with a service-level guarantee. Distillation (4.2) keeps cost down. |
| `claude_web` browser automation | Not a production path; can break at any time; likely against the site's terms | The Anthropic API only (already the first provider) |

**Budget:** licensed news and data is the biggest fixed cost. Get quotes before building features. Public
list prices are for terminals, not redistribution: Benzinga's Essential terminal plan is about $166/month,
and API redistribution is quoted separately.

### 6.2 🔴 SEBI positioning: decide one path

**Path A: news and information platform (lighter).** No recommendations, no targets, no "buy/sell", no
ranked stock lists. Rename "Top picks" to "Must-read stories" (it already ranks *stories*, not stocks;
make that obvious). Consider "positive/negative for the company" instead of "bullish/bearish". Show the
priced-in meter as history, not forecast. Add clear disclaimers. **Get a written legal opinion.** SEBI's Jan
2025 finfluencer rules show how strictly it separates "education" from "advice". For example, people doing
only education may not use price data from the last 3 months when naming securities. So don't call
yourself an education app while showing live prices.

**Path B: register as a Research Analyst (stronger moat).** Requirements include a graduate degree,
passing NISM Series XV, and the compliance setup. Once registered you can legally publish research. SEBI's
Jan 2025 guidelines require **disclosing how AI tools are used**, and the registered human stays fully
responsible for AI output. Performance claims go through PaRRVA. Most AI news apps can't take this path,
which makes it a moat, but it adds ongoing compliance work.

**My recommendation (estimate):** launch on Path A. Start Path B in parallel if you plan to offer anything
more than a verdict on relevance.

**Google Play:** every app must complete the **Financial features declaration**. The Financial Services
policy requires compliance with local law and disclosures in each country you target.

### 6.3 🔴 Production infrastructure

- Move the pipeline off the laptop: a small cloud VM or container, a job queue, and managed Postgres.
  Keep the local-first privacy design for bodies.
- **Latency target: publish → push in under 60 seconds** for filings and watchlist stories. That means
  polling or streaming instead of an hourly cron, and extraction triggered per article.
- **Separate staging from production.** Today the hourly cron runs *this working tree* against the real
  DB and Neon, so every half-finished edit is live.
- Monitoring and alerting on each stage, freshness, verified rate and cost per 1k articles.
  Backups, secret management, and a status page.

### 6.4 🟠 Android app basics

| Item | Note |
|---|---|
| **Framework** | Recommend **Expo (React Native) + TypeScript**. Reuses your API client, types, React Query hooks and domain logic. Better than a Capacitor web wrapper for notifications, widgets and background work. |
| Push notifications | FCM, with per-user quiet hours and the push budget (3.7) |
| **Home-screen widget** | "Your holdings: 2 stories today" (Android users use widgets; drives daily opens) |
| Offline cache + fast cold start | Commuters on patchy networks |
| Deep links + **share cards** | Every card shareable as an image with the "checked" badge: free distribution on WhatsApp |
| Account deletion in app + web | Play requirement |
| Data safety form, privacy policy, Financial features declaration | Play Console |
| **Developer account type** | A **personal** account created after Nov 2023 must run a closed test with **12 testers for 14 continuous days** before production. An **organization** account is exempt, and looks more trustworthy for a finance app. |
| Crash reporting + privacy-respecting analytics | e.g. Crashlytics/Sentry + PostHog |
| Tamil/Telugu/Hindi UI strings from day one | Not just translated content |

### 6.5 🟠 Privacy (DPDP Act)

The DPDP Rules were notified in Nov 2025. Consent-manager provisions start **13 Nov 2026**, and full
obligations apply from **13 May 2027**, with penalties up to ₹250 crore. Build consent, purpose limits,
deletion and breach handling in now. Holdings data is the most sensitive thing you'll hold, so the
on-device option (3.4) is both a compliance and a trust feature.

### 6.6 🟡 Business model

| Tier | What's in it |
|---|---|
| **Free** | Feed, daily brief, source labels, 5 watchlist alerts, 3 Tip Checks per week, Receipts page |
| **Pro** (price test, e.g. ₹99–199/month: **estimate, test it**) | My Exposure + MF look-through, priced-in meter, Overnight Bridge, unlimited alerts and Tip Checks, audio brief in regional languages |
| **B2B API** | Checked event feed + reaction statistics for SEBI analysts, brokers and fintechs. Aktai already sells tools to SEBI analysts, which shows demand. |

- **No ads.** Trust is the product.
- Google Play takes a service fee on subscriptions. In India, user choice billing is available (4
  percentage points lower when users pay through your own billing). The new fee structure reaches India on
  **30 Sep 2027**.

### 6.7 🟡 Metrics investors will ask for

D1/D7/D30 retention · weekly/monthly active ratio · % of users with holdings imported (the "aha" moment) ·
push open rate and **pushes per user per day (keep low)** · publish→push latency (p50/p95) · verified rate
· reaction-range calibration (coverage of the 80% interval) · Tip Checks shared per week (the growth loop)
· cost per 1k articles · free → Pro conversion.

### 6.8 🟡 Distribution

1. **Tip Checker share cards** in WhatsApp and Telegram groups (3.5)
2. A **WhatsApp Channel** carrying the 8 AM brief (headline + link only)
3. Public web pages per story and per stock, for search traffic (the web dashboard already exists)
4. Regional-language YouTube/Instagram shorts made from the audio brief (news, not tips: stay within the
   finfluencer rules)

### 6.9 🟡 People

A securities lawyer (on retainer), a compliance adviser (required if you take Path B), and eventually one
more engineer for mobile.

---

## 7. What would make building this easier (engineering foundations)

These aren't features, but each one speeds up every future change, whether you or I make it:

1. **Staging environment + a feature branch workflow.** Stop the hourly cron from running work in progress.
2. **A golden evaluation set:** 300–500 hand-checked articles (US + India) with correct tickers, event,
   tone and numbers. Every prompt or model change is scored against it before it ships.
3. **OpenAPI → generated TypeScript types**, shared by the web dashboard and the mobile app.
4. **Extraction versioning** (4.0). Also makes prompt experiments safe.
5. **A `CLAUDE.md`** with repo conventions, the "don't touch prod near :00" rule, how to run things
   safely, and the design rules you've already given me.
6. **Fixtures for the mobile app:** the dashboard's demo mode (`?demo=1`) is a good start; reuse its data.
7. **A single config for markets** (US, India, and later others) so adding a market is data, not code.

---

## 8. Roadmap with go/no-go gates

| Phase | Time | Build | Gate to move on |
|---|---|---|---|
| **0. Foundations** | Weeks 0–4 | Legal opinion (6.2); licensed data quotes and swap (6.1); cloud pipeline + staging (6.3); **extraction versioning + outcome logging** (4.0); golden set; organization developer account | Pipeline runs 14 days without the laptop; every data source licensed or primary |
| **1. Android MVP** | Months 1–3 | Expo app: feed, daily brief, watchlist, push under 60s, source labels (3.6), story timelines (3.10), Hindi. Share cards. Closed testing. | D30 retention target met (set it before launch); push opt-out < 20% **(estimate)** |
| **2. Signature features** | Months 3–6 | CAS import + My Exposure + MF look-through (3.4); Overnight Bridge (3.3); Tip Checker v1 with rules (3.5); priced-in meter v1 with statistics only (3.2); Receipts page with extraction accuracy (3.1); Pro tier | Holdings imported by ≥30% of active users **(estimate)**; Tip Checks shared weekly and growing |
| **3. Own models + public track record** | Months 6–12 | Ticker linker, distilled classifier, reaction model v2, source reliability, tip-risk model; Receipts shows reaction calibration; B2B API beta; decide on RA registration | Calibration holds on unseen months; B2B pilot customer |
| **4. Scale** | Year 2 | Exposure-graph shock propagation (GNN), more languages, iOS, more markets (the pipeline is already multi-market) | — |

---

## 9. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| SEBI treats tone labels or rankings as unregistered research | Medium | Path A framing + legal opinion; Path B as a backup; no buy/sell language anywhere |
| Data licence costs exceed early revenue | High | Primary sources first (filings, EDGAR); delayed prices; B2B API revenue; start with India + US large caps only |
| Zerodha, Groww or Perplexity copy the features | Medium | The Receipts history and outcome dataset can't be copied quickly; brokers have a conflict of interest on "trade less" |
| A wrong ticker or wrong number goes viral | Medium | Verifier + ticker linker + visible corrections log (part of Receipts) |
| Alert fatigue → uninstalls | High | Push budget, calm mode, relevance model |
| Look-ahead bias makes the reaction model look better than it is | High | Point-in-time data only; post-cutoff evaluation; publish calibration honestly |
| Solo-founder bandwidth | High | Phase gates; buy translation, speech, CAS parsing; build only the checking layer and the models in section 4 |

---

## 10. Don't do these

- No buy/sell calls, target prices, "multibagger" lists, or F&O tips.
- No in-app chat rooms or social feed: moderation burden, and a pump-and-dump channel.
- No ads.
- No scraping in the commercial product.
- Don't launch on iOS and Android at once. Android first (India's market), iOS in year 2.

---

## 11. Decisions only you can make

1. **Path A (news platform) or Path B (register as a Research Analyst)?** This changes wording,
   features and timeline.
2. **Data budget per month** for licensed news and prices. This sets what's possible in Phase 0.
3. **India-first with US as the bridge, or equal weight?** I recommend India-first: that's where the
   users are and where the cross-market angle is unique.
4. **App framework:** Expo React Native (recommended) or a Capacitor wrapper of the existing dashboard
   (faster to ship, weaker for widgets and notifications).
5. **Personal or organization Play developer account.** Organization skips the 12-tester rule and reads
   better for a finance app.

---

## Sources

**Competitors and market**
- [StockFlash](https://stockflash.in/) · [Aktai on Google Play](https://play.google.com/store/apps/details?id=com.aktailtd.app) · [Aktai](https://www.aktai.app/) · [Sentiment: Finance News](https://play.google.com/store/apps/details?id=com.pyse.sentiment&hl=en_CA) · [Markets AI](https://play.google.com/store/apps/details?id=com.marketsai.app)
- [Tickertape on Google Play](https://play.google.com/store/apps/details?id=in.tickertape&hl=en_IN) · [Tickertape review 2026](https://www.findmymoat.com/tools/tickertape) · [Pulse by Zerodha](https://pulse.zerodha.com/) · [Trendlyne alternatives 2026](https://www.strike.money/reviews/trendlyne-alternatives)
- [Perplexity Finance 101 (2026)](https://sidsaladi.substack.com/p/perplexity-finance-101-2026-the-complete) · [Best AI tools for stock research 2026](https://barebone.ai/resources/best-ai-tools-for-stock-research-2026)
- [NSE unique client codes hit 26 crore](https://www.sahi.com/news/nse-unique-client-codes-hit-26-crore-as-june-demat-additions-bounce-to-2-5-million-3932-PE1_COR) · [Demat additions surge to 3.3M (Aug 2026)](https://www.business-standard.com/markets/ipo/demat-additions-surge-to-3-3-mn-as-ipo-boom-drives-retail-investors-126090801443_1.html) · [23 crore demat accounts, how many are active?](https://www.nooreshtech.co.in/2026/09/india-has-23-crore-demat-accounts-but-how-many-investors-actually-show-up.html) · [Tier-2 cities drive demat growth](https://www.tribuneindia.com/news/business/tier-2-cities-drive-demat-account-growth-as-first-time-investors-enter-market/amp)

**Regulation (SEBI, DPDP, Google Play)**
- [SEBI Guidelines for Research Analysts (Jan 2025)](https://www.sebi.gov.in/legal/circulars/jan-2025/guidelines-for-research-analysts_90634.html) · [RAs/IAs must disclose AI tool use](https://www.taxmann.com/post/blog/sebi-mandates-ias-and-ras-to-disclose-use-of-ai-tools-in-providing-investment-advice-research-services-to-clients/) · [SEBI RA registration guide 2026](https://www.aktai.app/blog/sebi-research-analyst-registration-guide-2026)
- [SEBI restricts live market data in education content](https://www.businesstoday.in/markets/stocks/story/sebis-clampdown-on-finfluencers-cannot-use-live-stock-market-data-in-educational-content-462704-2025-01-31) · [Moneylife on finfluencer rules](https://mas360.moneylife.in/article/sebi-tightens-regulations-on-finfluencers-new-guidelines-for-educational-content-and-stock-market-advice/4724.html)
- [SEBI operationalises PaRRVA (Apr 2026)](https://www.sebi.gov.in/media-and-notifications/press-releases/apr-2026/sebi-operationalises-past-risk-and-return-verification-agency-parrva-_101187.html) · [PaRRVA explained](https://www.business-standard.com/finance/personal-finance/parrva-explained-sebi-s-verification-tool-to-check-performance-claims-125121000535_1.html) · [PaRRVA enrolment extension](https://www.outlookmoney.com/invest/sebi-extends-parrva-enrolment-date-for-investment-advisors-research-analysts)
- [SEBI F&O study: 91% of traders lost in FY25](https://www.business-standard.com/markets/news/net-losses-of-traders-in-fo-widens-in-fy25-sebi-study-125070701221_1.html) · [₹1.06 lakh crore lost in FY25](https://www.moneylife.in/article/106-lakh-crore-lost-by-individual-traders-in-fo-in-fy2425-govt-confirms-sebi-action-on-4-entities-for-market-abuse/79124.html)
- [SEBI cracks down on finfluencer pump-and-dump network (May 2026)](https://aninews.in/news/business/sebi-cracks-down-on-finfluencer-pump-and-dump-network-warns-retail-investors-against-social-media-stock-tips20260523110908/) · [SEBI investor note on pump-and-dump](https://investor.sebi.gov.in/pdf/Pump%20and%20Dump%20Scam%20final.pdf)
- [DPDP Rules 2025 timeline](https://www.consently.in/blog/dpdp-rules-2025-implementation-timeline-india) · [Fisher Phillips on DPDP deadlines](https://www.fisherphillips.com/en/insights/insights/indias-new-data-privacy-rules-are-here)
- [Google Play Financial Services policy](https://support.google.com/googleplay/android-developer/answer/13161491) · [Financial features declaration](https://support.google.com/googleplay/android-developer/answer/13849271?hl=en) · [Testing requirements for new personal accounts](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en) · [Expanded billing choice and lower fees (Jun 2026)](https://android-developers.googleblog.com/2026/06/play-expanded-billing.html) · [India billing requirements](https://support.google.com/googleplay/android-developer/answer/13306652?hl=en)

**Data and licensing**
- [Finnhub commercial pricing](https://finnhub.io/pricing-startups-and-enterprise) · [Benzinga APIs](https://www.benzinga.com/apis/) · [Financial news APIs compared (redistribution rights)](https://qveris.ai/guides/financial-news-api-for-ai-agents) · [Benzinga vs Finnhub](https://mediawatcher.ai/blog/benzinga-api-vs-finnhub-vs-investment-watcher-which-news-api-actually-moves-desks/)
- [NSE paid real-time data](https://www.nseindia.com/static/market-data/real-time-data-subscription) · [TrueData market data APIs](https://www.truedata.in/market-data-apis) · [Yahoo Finance API status 2026](https://marketxls.com/blog/yahoo-finance-api-ultimate-guide) · [yfinance docs](https://ranaroussi.github.io/yfinance/)
- [CDSL as Account Aggregator data provider](https://www.cdslindia.com/Investors/FIP.html) · [NSDL as data provider](https://nsdl.co.in/value/Financial_Information_Provider.php) · [State of Account Aggregator 2026](https://casparser.in/blog/state-of-account-aggregator-2026/) · [CASParser](https://casparser.in/)

**Research (models)**
- [Buy the Rumor, Sell the News: When Is News Priced In? (arXiv 2608.14014)](https://arxiv.org/pdf/2608.14014)
- [Detecting Lookahead Bias in LLM Forecasts (arXiv 2512.23847)](https://arxiv.org/pdf/2512.23847)
- [LLM-Enhanced Dynamic Financial Knowledge Graphs for Cross-Entity Signal Propagation (arXiv 2607.10932)](https://arxiv.org/pdf/2607.10932)
- [Agentic AI Nowcasting Predicts Stock Returns (arXiv 2601.11958)](https://arxiv.org/pdf/2601.11958)
- [LLMs in equity markets: survey (Frontiers, 2025)](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1608365/full)
- [ML Kit GenAI Summarization API](https://developers.google.com/ml-kit/genai/summarization/android) · [On-device inference on Android (Jul 2026)](https://android-developers.googleblog.com/2026/07/android-on-device-inference.html)
