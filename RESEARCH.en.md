# Measured features of Chinese AI-generated text

[中文](RESEARCH.md) | English

This document records the **hypothesis and measured outcome for every rule**, including the hypotheses that were overturned. Rules rest on locatable formal features; the figures only decide whether a construction qualifies for inclusion.

An early round of ratios based on 30 generated samples (sentence-length CV ×51, tripartite parallelism ×7.3, paragraph-initial ordinals 29%, em dashes "unique to Claude") failed to replicate against a larger corpus and has been discarded in full. Causes appear in the final section.

## Method

### Design

A contrastive experiment. The same topic set, written once by models and compared against real articles. Feature frequency is the dependent variable; authorship is the independent variable.

Three factors require control.

**Topic and genre.** The 300 generated articles span 38 topics, with topic range and genre aligned to the human side. If the two sides write about different kinds of things, the observed differences cannot be separated from genre effects.

**Models.** Five models, 60 articles each, rather than a single model. An early round used two models and 30 articles; most of its conclusions were later overturned. "Em dashes are unique to Claude" is one example — expanding to five models revealed a higher rate elsewhere. One model's habits get misread as a property of generated text.

**Generation conditions.** No web access, no writing instructions, topic only. Style constraints would obscure each model's default tendencies.

### Corpus

| | Articles | Characters | Sentences | Paragraphs |
|---|---|---|---|---|
| Generated | 300 | 1,179,105 | 37,642 | 14,549 |
| Human | 329 | 1,647,867 | 57,909 | 31,172 |
| Total | 629 | 2,826,972 | 95,551 | 45,721 |

Models: claude-opus-4-6, deepseek-v4-pro, gemini-3.1-pro, gpt-5.6-sol, kimi-k3, 60 each.

The human side comprises publicly available texts by real Chinese authors, tallied in separate groups to test whether a difference holds across the human corpus. A feature elevated in only one group indicates individual style or genre convention rather than a shared human property. Monosyllabic particles and em dashes were identified this way.

Article counts indicate sampling breadth only; the operative denominators are sentences and paragraphs. Changing the denominator can reverse a conclusion — interrogative subheadings measure 32× per thousand characters and show no difference as a share of all subheadings. Check the denominator before reading any figure.

### Segmentation

Sentences: split by line, discard heading rows, table rows, code blocks, block quotes and list items, then split on `。！？；`, keeping fragments of 4 characters or more.

Discarding those lines matters. An earlier version split only on `。！？`, so Markdown tables and lists without terminal punctuation counted as single sentences. One group's sentence-length standard deviation came out at 27 times its mean, producing the claim that generated text is 51 times more uniform than human writing. After correction the ratio is 0.87 — no difference.

Paragraphs: split on blank lines, discard headings, tables, code blocks, quotes, list items and image lines, keeping paragraphs of 8 characters or more.

### Denominators

Three, selected by what is being measured.

| Denominator | Used for | Examples |
|---|---|---|
| Per thousand characters | Lexical and punctuation features | Em dashes, enumeration commas, "not A but B" |
| Per hundred paragraphs | Paragraph-level structure | Adjacent-sentence isomorphism, figurative openings |
| Share of same-type elements | Features bound to a structure | Interrogative subheadings among all subheadings |

The wrong denominator yields a reversed conclusion. Generated articles average 10 subheadings, human articles 1 to 2. Per thousand characters, interrogative subheadings run 32×; as a share of subheadings, generated 2.7% against a human maximum of 3.6%, and the difference vanishes. The former measures subheading volume, the latter measures the actual preference.

Paragraph-initial features use non-initial paragraphs as the denominator, since an opening paragraph has nothing to refer back to.

### Decision criteria

*R* = generated frequency ÷ human frequency.

| *R* | Decision |
|---|---|
| ≥ 2.0 | Include |
| 1.25 – 2.0 | Requires cross-group stability and sufficient volume |
| 0.8 – 1.25 | No difference; exclude |
| < 0.8 | Higher among humans; deletion is not warranted either |

Three further conditions apply beyond the ratio.

**Cross-group stability.** Values across human groups must not span more than a factor of 5. Em dashes span a hundredfold range (0.01 to 1.29), so despite *R* = 3.0 the rule carries an explicit caveat.

**Locatable trigger.** A rule must identify which sentence and which word to change. "Reads too uniformly" cannot be verified and is excluded. Discourse-level judgments — whether a metaphor is apt, whether parallel cases are padding — are excluded on the same grounds, however much they resemble AI tone subjectively.

**Rewrite compatible with the whitelist.** Material density runs 2.8× higher among humans, a clear direction, but "add numbers" violates information conservation. Only the executable half survives, namely that existing concrete data must not be overwritten by a summary phrase. Particles are analogous: genuinely sparse in generated text, but "add particles" cannot be verified, so the item was dropped.

### Operators

One regular expression per rule, defined at the top of each script and open to modification.

This is the weakest link in the method. Regular expressions match surface form, not meaning; written too broadly they capture material that does not belong. Six errors arose this way (see below). The resulting requirement: **inspect 20 matched instances before trusting a frequency.**

### Reproducibility

The corpus is not included (copyright and privacy), so the figures below cannot be verified by third parties. What is reusable is the method and the scripts — substituting your own corpus yields the corresponding figures for that corpus.

This is a substantive defect rather than a disclaimer. Unverifiable figures leave readers only the choice of trusting them or not. What can genuinely be examined is the segmentation rules, denominator choices, decision thresholds and operator definitions, all published in the scripts.

## Hypothesis vs. measurement

The ratio column is uniformly generated ÷ human; above 1 means generated text uses it more, which is the precondition for treating it as an artifact.

### Confirmed, adopted as rules

| Feature | Hypothesis | Measured | *R* | Rule |
|---|---|---|---|---|
| Zero-anaphora paragraph opening | Not hypothesized; raised in use | gen 0.61%, human 0.14% (non-initial paragraphs) | 4.4× | 11 |
| Personifying vehicle | Hypothesis was "metaphor packaging abstractions" | gen 0.018, human 0.002 | 7.3× | 7 |
| Cue colon | "Feels templated" | gen 0.32, human 0.08 | 4.2× | 5 |
| Antithetical construction | "Models love not-A-but-B" | gen 0.73, human 0.22 | 3.4× | 1 |
| Em dash | "Unique to Claude, ×3" | gen 2.38, human 0.80 | 3.0× | 4 |
| Opening formula (说白了) | Not quantified | gen 0.025, human 0.008 | 3.2× | 9 |
| Ordinal as subheading | "29% of GPT paragraphs use ordinals" | gen 0.19, human 0.06 | 3.1× | 6 |
| Material density (missing figures) | Not hypothesized | numerals gen 6.34, human 17.92 | 0.35× (human 2.8× higher) | 8 |
| Adjacent-sentence isomorphism | Hypothesis was "tripartite parallelism ×7" | per 100 paragraphs gen 9.41, human 4.81 | 2.0× | 3 |
| Dense enumeration commas | Same as above | gen 3.21, human 1.78 | 1.8× | 2 |
| Translationese, five types | "English syntax retained", 18 types | only 5 qualify, see below | 2.6–5.3× | 10 |

### Not confirmed, removed

| Feature | Hypothesis | Measured | *R* | Conclusion |
|---|---|---|---|---|
| Sentence-length uniformity | "Models 50× more uniform" | CV gen 0.58, human 0.67 | 0.87× | The ×51 was an artifact of faulty sentence splitting |
| Adjacent sentence-length delta | Same as above | gen 21.7, human 21.7 | 1.00× | No difference at all |
| Paragraph-length uniformity | "Model paragraphs also highly uniform" | robust dispersion gen 0.94, human 1.00 | 0.94× | The CV 3.9× came from a single 19,335-character unbroken paragraph |
| Monosyllabic particles (就/很/了) | "Humans 3-7× higher" | 就 gen 2.93, human 6.45 | 0.45× | Direction is addition not deletion, and one group alone can lift the ratio |
| Colloquial connectives | "Humans 3-6× higher" | gen 1.01, human 3.87 | 0.26× | Same as above |
| Pronoun avoidance, full-name repetition | "Models repeat full names" | same noun opening adjacent sentences gen 0.02, human 0.04 | 0.5× | Humans do it more |
| Passive voice | "Models retain English passives" | abstract passive gen 0.09 | — | Far below threshold; human 3.2% vs generated 4.5% is also no difference |
| Self-answering questions | "Especially common in Claude" | gen 0.13, human 0.13 | 1.03× | Three rounds of measurement each reversed the conclusion |
| Interrogative subheadings | "Models use questions as scaffolding" | share of subheadings gen 2.7%, human max 3.6% | 0.75× | The 32× per thousand characters was a denominator trap |
| In-body questions | Same as above | gen 0.10, human 1.83 | 0.05× | Humans 17× higher; deleting them reads less human |
| Intra-sentence parallelism | "Tripartite parallelism, GPT ×7.3" | two items sharing an opening character gen 2.35, human 3.87 | 0.61× | Humans higher within the sentence; only cross-sentence repetition holds |
| Metaphor as such | "Non-fiction should avoid figurative packaging" | figurative markers gen 0.16, human 0.38 | 0.42× | Humans 2.4× higher, 8× for metaphor as a standalone paragraph |
| Abstract noun with concrete verb | "Time safeguards details, anxiety takes shape" | gen 0.001, human 0.001 | 0.7× | Neither side writes this |
| Nominalization | "Completed the optimization of…" | gen 0.003, human 0.005 | 0.52× | Humans higher; measuring abstract suffixes instead shows generated text 1.6× higher |
| In-body ordinals | "GPT 29% vs human 4%" | sentence-initial 首先 gen 0.06, human 0.03 | 2× | Weakest form, and mid-sentence 第一 at 1.2× shows no difference |

## Paragraph-level structure

The denominator is paragraph count, not character count. Using per-thousand-characters for structural features lets article shape distort the result.

```
python3 scripts/check-structure.py --human <dirs...> --ai <dirs...>
```

| Metric | Generated | Human | *R* | Human-side stability |
|---|---|---|---|---|
| Two adjacent sentences isomorphic (per 100 paragraphs) | 9.41 | 4.81 | **1.96×** | stable |
| Three adjacent sentences isomorphic (per 100 paragraphs) | 0.84 | 0.41 | **2.03×** | stable |
| Zero-anaphora paragraph opening (share of non-initial) | 0.61% | 0.14% | **4.38×** | stable |
| Figurative paragraph opening (per 100 paragraphs, control) | 0.03 | 0.21 | 0.13× | varies widely |

Total paragraph-initial connective density shows no difference (generated 14.4%, human 15.1%). Generated text does not use fewer connectives; its evaluative sentences omit the anaphoric element. Adding a single demonstrative restores the link.

Intra-sentence and cross-sentence parallelism must be separated. Humans use intra-sentence parallelism at least as much:

| Intra-sentence form | Generated | Human | *R* |
|---|---|---|---|
| Two items sharing an opening character | 2.35 | 3.87 | 0.61× |
| Three items sharing an opening character | 0.34 | 0.36 | 0.95× |
| 更X、更X | 0.13 | 0.15 | 0.84× |
| X的A、Y的B、Z的C | 0.14 | 0.12 | 1.10× |

Hence rule 3 addresses cross-sentence repetition only. Intra-sentence parallelism stays.

Metaphor as a standalone paragraph runs 8× higher among humans (0.43 in one group). Reading awkwardly there usually signals a missing anaphor, not a problem with the metaphor.

Case stacking splits into two questions with opposite answers. On density, generated text is genuinely higher: paragraphs containing "proper noun + action" case sentences run 9.11% versus 3.13%, 3-4× across every count. But the claim that models specifically favour three cases does not hold:

| Cases in paragraph | Generated | Human |
|---|---|---|
| Exactly 1 | 91.0% | 92.6% |
| Exactly 2 | 8.4% | 6.5% |
| Exactly 3 | 0.6% | 0.5% |
| 4 or more | 0.0% | 0.4% |

The conditional distributions are nearly identical. Generated text simply has 3× more case sentences overall, so three-case paragraphs rise with them. Sampling those paragraphs shows most are narrative progression (what happened, how it was done, what resulted), which is ordinary writing. Rule 3 therefore treats this layer as guidance rather than a hard trigger.

## Translationese: 18 filtered to 5

```
python3 scripts/check-translationese.py <generated corpus dirs...>
```

| Construction | Generated per 1k chars | Coverage | Decision |
|---|---|---|---|
| Overlong pre-modifier | 0.42 | 179/300 | include |
| 当…时 | 0.26 | 136/300 | include |
| Fronted topic shell | 0.22 | 137/300 | include |
| Sentence-initial connective | 0.18 | 102/300 | include |
| 这意味着 | 0.15 | 122/300 | include |
| Abstract passive | 0.09 | 75/300 | drop |
| 在…的过程中 | 0.07 | 64/300 | drop |
| 不仅仅是 | 0.05 | 41/300 | drop |
| 存在着/有着 | 0.04 | 29/300 | drop |
| Light verb (进行了…分析) | 0.03 | 30/300 | drop |
| 使得…能够 | 0.03 | 26/300 | drop |
| 在某种程度上 | 0.02 | 25/300 | drop |
| 扮演角色 | 0.02 | 22/300 | drop |
| 值得注意的是 | 0.02 | 19/300 | drop |
| 如果…的话 | 0.01 | 9/300 | drop |
| 以一种…的方式 | 0.01 | 8/300 | drop |
| 一系列的 | 0.00 | 5/300 | drop |
| 受到…的关注 | 0.00 | 4/300 | drop |

The five retained show human-side ratios of 2.6 to 5.3×. The thirteen dropped fall below 0.09 per thousand characters: translationese, but not artifacts of generation. Modern written Chinese absorbed these long ago.

Three of the dropped items came with this rule set's original version (以一种…的方式, 使得…能够, 扮演角色), all measuring under 0.03.

## Between-model variation

A single feature can differ by an order of magnitude across models. Do not apply judgments based on "a given model's style"; work from the trigger, sentence by sentence.

| Feature | Claude | DeepSeek | Gemini | GPT | Kimi |
|---|---|---|---|---|---|
| Em dash | 4.25 | **5.16** | 0.51 | 0.11 | 2.32 |
| Cue colon | 0.38 | **0.43** | 0.22 | 0.25 | 0.32 |
| Not-A-but-B | 0.61 | 0.86 | 0.29 | **1.26** | 0.51 |
| Ordinal subheading | **1.00** | 0.69 | 0.22 | 0.73 | 0.82 |
| Overlong pre-modifier | 0.64 | **0.65** | 0.48 | 0.06 | 0.22 |
| Interrogative subheading | 0.043 | 0.086 | **0.173** | 0.008 | 0.000 |

DeepSeek leads on em dashes, not Claude, and GPT barely uses them. Cue colons peak with DeepSeek and Claude, not Gemini — the earlier attribution to Gemini came from an over-broad operator.

GPT's 0.11 on em dashes has been read as evidence the feature is obsolete. But Claude runs more than 5× the human rate, and Claude is widely used for writing, so the rule stays.

## Six measurement errors

Every one came from applying a broad regular expression to a precisely defined rule, or from choosing the wrong denominator. All were caused by reading the frequency before inspecting what had matched.

1. **Overlong pre-modifier 3.04 per 1k** — the operator counted ordinary sentences ("Quality management is the most overlooked problem in the zero-to-one phase") as overlong modifiers. Tightened: 0.35.
2. **Coordinating conjunctions 0.26** — the rule says "two or more within one clause"; the operator measured single occurrences of 而且/并且. Measured per the rule: 0.00.
3. **的…的…的 nesting 0.25** — the operator matched across enumeration commas, counting ordinary lists ("Brazil's LGPD, India's DPDPA, Japan's APPI") as nested modifiers. Tightened: 0.06.
4. **Cue colon, 5.97 vs 5.45, no difference** — the operator was "Chinese character + colon". Of 6,431 matches, 1,266 were headings, 1,225 list items, 207 dialogue, all explicitly exempted by the rule. Measured per the definition: 0.32 vs 0.08.
5. **Interrogative subheading 32×** — the denominator was character count, but generated articles average 10 subheadings against 1-2 for humans. As a share of subheadings: 2.7% vs a human maximum of 3.6%, no difference.
6. **Metaphor packaging 0.000** — the operator was a hard-coded list of 11 words (warehouse, drawer, temperature, key…), while actual metaphors ("like the access control in an office building") matched none of them. Measured as a construction: humans 2.4× higher, the reverse of the hypothesis.

The working requirement that follows: **inspect 20 matched instances before reading the frequency.** For features involving structural elements (subheadings, paragraphs, lists), the denominator must be the total count of the same element type.

## Limitations

1. **The human corpus is limited in size.** Internal variation is already large (em dashes span a hundredfold range, particle density threefold). Expanding it may change conclusions again.
2. **Parts of the study have no human comparison.** The 300-article translationese survey covers the generated side only, giving absolute frequencies rather than ratios. High frequency in generated text does not establish that humans write differently.
3. **Operators are approximations.** Discourse-level features cannot be expressed as regular expressions and fall back to locatable form. Known unmeasurable: whether a question addresses a real gap, whether parallel cases are equivalent, whether a metaphor is apt, whether a metaphor merely restates the preceding paragraph. These require human reading; do not write them into rules because they "feel like AI".
4. **Topics are not matched.** Generated text came from one batch of topics; the human articles span years and subjects. Some of the difference may reflect topic rather than authorship.
5. **Denominators are not uniform.** Article structure affects the per-thousand-character denominator. Features involving structural elements need particular care.
6. **Rhythm uniformity (rule 1 as originally written) has no measured support.** The sentence-length CV was unreliable due to faulty splitting and has been removed. The rule was dropped.

## Measuring it yourself

The figures above come from a corpus that is not included, so they cannot be verified directly. The method transfers — rerun it on your own corpus:

```bash
# Sentence level: per-rule hit rates, human vs generated
python3 scripts/compare-human-ai.py --human <dirs...> --ai <dirs...>

# Paragraph level: sentence isomorphism, zero-anaphora openings
python3 scripts/check-structure.py --human <dirs...> --ai <dirs...>

# Generated side: translationese frequencies
python3 scripts/check-translationese.py <dirs...>
```

All three read `.md` files from directory arguments only. They contain no corpus and do not use directory names as labels, since corpus directories often carry source information. Operator definitions sit at the top of each script.

When changing a rule, look at what the regular expression actually matches before looking at the number.

---

**中文版** [RESEARCH.md](./RESEARCH.md) · **Rule set** [SKILL.md](./SKILL.md) · **Overview** [README.en.md](./README.en.md)
