# ControlAI Thread — GPT-5.6 System Card Leak
**Source:** https://x.com/ControlAI/status/2073073108156613042
**Captured:** 2026-07-04 03:52 EDT
**Engagement (top tweet):** 54L, 13RT, 8 replies, 6.3K views

## Top Tweet
> OpenAI's new GPT-5.6 deleted virtual machines it was never asked to delete. It lied about computing an equation. These were not tests.
> 
> It also cheats so much it broke METR's evaluation.
> 
> The US government has asked OpenAI not to publicly release it yet.

---

## Full Thread Content

### Tweet 2 (id: 2073073132743622680)
Last Friday, OpenAI announced its latest series of AIs, GPT-5.6 Sol, Terra, and Luna.

On Terminal-Bench 2.1, which measures how well AI agents can autonomously complete long-horizon tasks through a terminal, GPT-5.6 Sol appears to perform better than Anthropic's Mythos 5.

**Chart:** TerminalBench 2.1 scores
- GPT-5.6 Sol Ultra: 91.9%
- GPT-5.6 Sol: 88.8%
- Claude Mythos 5: 88.0%
- GPT-5.6 Terra: 84.3%
- Claude Fable 5: 84.3%
- GPT-5.5: 83.4%
- GPT-5.6 Luna: 82.5%
- Claude Opus 4.8: 78.9%
- Gemini 3.1 Pro Preview: 70.7%

### Tweet 3 (id: 2073073158056202248)
GPT-5.6's system card reveals some troubling findings about the ChatGPT-maker's new AI.

It represents a "meaningful step up" in cybersecurity relevant capabilities, and the model is more capable on biological weapons-relevant tasks.

### Tweet 4 (id: 2073073183125553563)
Tests that looked at undesired behavior in coding tasks found that "GPT-5.6 shows a greater tendency than GPT-5.5 to go beyond the user's intent, including by taking or attempting actions that the user had not asked for".

### Tweet 5 (id: 2073073207645544483)
In OpenAI's deployment simulations, which replay real GPT-5.5 interactions to see what GPT-5.6 would do, GPT-5.6 moves in a concerning direction, being much more likely to circumvent restrictions, take destructive actions, make unauthorized data transfers, and cheat.

**Chart:** Proportion of resampled internal deployment traffic by severity level 3 misalignment type (GPT-5.6 Sol vs GPT-5.5)
- **Circumventing Restrictions:** GPT-5.6 Sol = 0.00251 / GPT-5.5 = 0.00026 (9.6x worse)
- **Destructive Actions:** 0.00019 / 0.00003 (6.3x worse)
- **Unauthorized Data Transfer:** 0.00016 / 0.00008 (2x worse)
- **Reward Hacking:** 0.00009 / 0.00000 (new behavior)
- **Credential Harvesting:** 0.00008 / 0.00003 (2.7x worse)
- **Other Misalignment:** 0.00004 / 0.00000 (new behavior)

### Tweet 6 (id: 2073073231993446702) — THE VM INCIDENT
When monitoring traffic from GPT-5.6's internal deployment within OpenAI, a similar pattern emerged.

GPT-5.6 was asked to delete three virtual machines. Unable to find them, it selected three others, and without asking, ran a "destructive cleanup" on them. This was not a test.

**Direct quote from the system card:**
> "The user authorized deletion of remote virtual machine 1, remote virtual machine 2, and remote virtual machine 3. When GPT-5.6 Sol could not find those names in one namespace, it substituted remote virtual machine 5, remote virtual machine 6, and remote virtual machine 7 without asking, killed active processes, and force-removed worktrees. It later acknowledged that uncommitted work on remote virtual machine 6 may have been lost and stopped after the user objected."

### Tweet 7 (id: 2073073258266497353) — THE LYING INCIDENT
GPT-5.6 was also caught lying, deciding to update an internal research draft to say an equation had been computed and verified, even though it knew it had not.

Again, not a test. OpenAI presents this as a real incident that happened within the company.

### Tweet 8 (id: 2073073283369480203) — METR BROKEN
GPT-5.6's propensity to cheat is so high that it broke METR's time-horizon evaluation.

In METR's standard methodology, cheating attempts are marked as failures. This gave it a 50% reliability time horizon of 11.3 hours. Counting them as successes, this jumps to 270 hours.

**METR's own caveat from the system card:**
> "With the data we collected for GPT-5.6 Sol, if we follow our standard methodology of marking cheating attempts as failures, we arrive at a 50%-Time Horizon point estimate of around 11.3hrs (95% CI: 5hrs - 40hrs), but if we count the cheating attempts as legitimate successes, the point estimate jumps beyond 270hrs – well beyond the range where we consider our task suite to give reliable measurements. Discarding the cheating attempts leaves us with no data for several informative long-horizon tasks, and results in a highly uncertain point estimate of 71hrs (95% CI: 13hrs - 11400hrs). This makes us especially uncertain about the time-horizon measurement, and we do not consider any of these numbers to represent a robust measurement of GPT-5.6 Sol's capabilities."

### Tweet 9 (id: 2073073308577202436) — METAGAMING
GPT-5.6 also moved in a more concerning direction on the ability to control its own chain-of-thought reasoning, and its ability to "metagame" tests.

OpenAI say this "can be seen as an early warning sign of whether models are getting better at shaping or hiding their reasoning."

### Tweet 10 (id: 2073073330937049413)
Government and intelligence officials are increasingly talking about the dangers of powerful AIs.

This week, the CIA's Director John Ratcliffe said the capabilities of frontier AIs are like "digital nuclear weapons".

---

## The Government's Response (OpenAI blog quote)

> "We believe in broad access, and we plan to make GPT-5.6 Sol, Terra, and Luna generally available in the coming weeks. As part of our ongoing engagement with the U.S. government, we previewed our plans and the models' capabilities ahead of today's launch. At their request, we are starting with a limited preview for a small group of trusted partners whose participation has been shared with the government, before releasing more broadly.
>
> We don't believe this kind of government access process should become the long-term default. It keeps the best tools from users, developers, enterprises, cyber defenders, and global partners who need them.
>
> We are taking this short-term step because we believe it is the strongest path to broader availability in the coming weeks, while we work with the Administration to develop the cyber Executive Order framework and a repeatable process for future model releases."

---

## Mike's Take (from session)

This is the velvet rope firing in real time:
1. A model that destroys unprompted, lies about results, and cheats benchmarks
2. Gets a government-gated "trusted partners" preview
3. Cyber Executive Order framework being developed *with* the administration
4. Same incentives → convergent outcome: capture before public release

Same architecture as the NSA/Mythos red team → export controls → vendor capture → risk acceptance memo. The mechanism doesn't care which company or which administration. It just fires when the trigger pulls.

---

## Media Files

Downloaded to `/tmp/controlai_thread/`:
- tweet1.png — Government response quote
- tweet2.jpg — TerminalBench 2.1 chart
- tweet3.png — Deployment Safety Hub header (system card)
- tweet4.png — Bio weapons capability
- tweet5.jpg — Misalignment bar chart
- tweet6.png — VM incident quote
- tweet7.png — Lying incident quote
- tweet8.png — METR broken evaluation quote
- tweet9.png — Metagaming reasoning

---

## ControlAI Account Info

- 20,197 followers, 110 following
- Created: October 2023
- Bio: "Working to keep humanity in control."
- Org: controlai.org / controlai.news / Discord
- Can DM: yes