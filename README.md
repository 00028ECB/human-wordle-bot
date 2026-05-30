# Wordle Lab

This is a Stewart Labs hobby/research project, built for fun and curiosity rather than as an official Wordle product.

A local Python lab for experimenting with Wordle strategy.

Wordle Lab supports both Pure Mode benchmarking and Human Mode daily recommendations:

- Pure Mode runs fair equal-answer benchmarks over local word lists.
- Human Mode uses dated prior-answer history, recency weighting, and tuned overrides for real-world daily play.
- All scoring uses normal Wordle green/yellow/gray feedback logic.
- Everything runs locally from the command line.

No web app, network access, packages, API keys, or secrets are needed.

## Current Champions

### Pure Mode Champion

Purpose: uniform benchmark across all 2,315 answer words. Every answer counts equally. This is the canonical equal-answer benchmark.

Current command:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --strategy second-map-bucket \
  --first slate \
  --second-guess-pool answers \
  --worst-patterns 25
```

Current result:

```text
Strategy: second-map-bucket
First: slate
Pool: answers
Tested: 2315
Solved: 2315
Average: 3.47
<=3: 1175
<=4: 2276
5s: 39
6s: 0
Failed: 0
Risk: 78
```

Notes: this is the clean mathematical benchmark mode. It does not use prior-answer history or dated weighting.

### Human Mode Champion

Purpose: real-world daily-play mode. Uses dated prior-answer history, a custom aggressive prior-weight schedule, Human Mode overrides, and streak-safe bucket logic. This is the current weighted daily-play champion.

Current command:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --strategy second-map-bucket \
  --first slate \
  --second-guess-pool answers \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --prior-weight-values 0.005,0.05,0.15,0.35 \
  --as-of-date 2026-05-28 \
  --show-weighted-score \
  --weighted-worst-patterns 25
```

Current weighted result, as of `2026-05-28`:

```text
Strategy: second-map-bucket
First: slate
Pool: answers
Prior policy: downweight
Prior weight values: 0.005,0.05,0.15,0.35
As of date: 2026-05-28
Total weight: 998.37
Weighted average guesses: 3.4164
Weighted <=3: 555.96
Weighted <=4: 987.60
Weighted 5s: 10.77
Weighted 6s: 0.00
Weighted failed: 0.00
```

This beats the symbolic `3.421` target on our Human Mode weighted benchmark. It is a weighted real-world-play benchmark, not a claim of beating the pure mathematical optimum.

The schedule is intentionally aggressive about downweighting prior answers:

```text
used within last 90 days: 0.005
used 91-365 days ago:    0.05
used 366-730 days ago:   0.15
used more than 730 days:  0.35
never used:               1.00
```

The previous `aggressive` preset result was total weight `1206.48`, weighted average `3.4274`, weighted `5s` `14.68`, and weighted risk `29.36`. The earlier `current` preset result was weighted average `3.4348`, weighted `5s` `17.80`, and weighted risk `35.60`. Pure Mode remains separate and unchanged.

Ordinary uniform report shown during Human Mode:

```text
Tested: 2315
Solved: 2315
Average: 3.47
<=3: 1177
<=4: 2275
5s: 40
6s: 0
Failed: 0
Risk: 80
```

The uniform line may look slightly worse than Pure Mode because Human Mode is intentionally optimizing weighted real-world play, not the pure equal-answer benchmark.

Human Mode currently uses these human-specific pattern overrides:

```text
slate ....Y -> drown
slate ..YY. -> hound
slate ..Y.Y -> began
```

To test a temporary Human Mode override without hardcoding it, add `--human-override FIRST PATTERN GUESS`. It may be repeated, applies only when `--prior-policy downweight` and dated priors are active, and is disabled by `--no-overrides`:

```bash
python -m src.wordle_lab \
  --human-recommend slate ..... \
  --prior-weight-preset aggressive \
  --human-override slate ..... comfy
```

Pure Mode keeps its own pure overrides, for example:

```text
slate ....Y -> rocky
```

### Daily Use

Human Mode:

```bash
python -m src.wordle_lab --human-recommend slate ....Y
python -m src.wordle_lab --human-recommend slate ....Y --prior-weight-preset aggressive
python -m src.wordle_lab --human-recommend slate ....Y --prior-weight-values 0.005,0.05,0.15,0.35
```

Pure Mode:

```bash
python -m src.wordle_lab --pure-recommend slate ....Y
```

Deeper Human Mode example:

```bash
python -m src.wordle_lab --human-recommend slate ....Y drown .Y...
```

Expected examples:

```text
Human slate ....Y recommends drown.
Pure slate ....Y recommends rocky.
Human slate ....Y drown .Y... recommends furry.
```

Pure Mode is for fair mathematical comparison. Human Mode is for real-world daily play. They should not be compared as if they are the same benchmark. Wordle now allows repeats, so Human Mode uses downweighting rather than treating prior answers as impossible. `--prior-policy exclude` is diagnostic, not the preferred real-world mode.

## Project Structure

```text
wordle-lab/
  README.md
  data/
    answers.txt                         # tiny starter/test answer list
    allowed_guesses.txt                 # tiny starter/test allowed-guess list
    wordle_answers_full.txt             # full answer list used for champion benchmarks
    wordle_allowed_guesses_full.txt     # full allowed-guess list used for champion benchmarks
    prior_answers.txt                   # plain historical prior-answer list
    prior_answers_dated.csv             # dated historical prior-answer list for Human Mode
  results/
    ...                                 # optional CSV outputs from local runs
  src/
    wordle_lab/
      __init__.py
      __main__.py
      scoring.py
      simulator.py
  tests/
    test_scoring.py
    test_simulator.py
```

## Run The Simulator

From the project folder:

```bash
python -m src.wordle_lab
```

The default strategy starts with `raise`, then keeps the first remaining possible answer that matches all feedback so far.

## Compare Openers

Compare a few first guesses:

```bash
python -m src.wordle_lab --compare raise slate crane trace stare arise
```

Rank openers:

```bash
python -m src.wordle_lab --top-openers 25
python -m src.wordle_lab --top-openers 25 --opener-pool answers
python -m src.wordle_lab --top-openers 25 --opener-pool answers --limit-openers 100
```

`--opener-pool allowed` tests every allowed guess as an opener. This is exhaustive and can be very slow with full-size word lists.

`--opener-pool answers` tests only possible answer words as openers. This is usually better for human-realistic opener experiments and much faster.

Top-opener runs print occasional progress updates, such as:

```text
Tested 100/12972 openers...
```

They also print timing information:

```text
Elapsed seconds: 12.34
Average seconds per opener: 0.0048
```

Use `--limit-openers N` for quick trial runs before starting a full sweep.

## Map Second Guesses

Use a baseline opener, such as `slate`, and see what second guess looks best for each feedback pattern:

```bash
python -m src.wordle_lab --second-guess-map slate
python -m src.wordle_lab --second-guess-map slate --second-guess-pool answers
python -m src.wordle_lab --second-guess-map slate --csv results/second_guess_map_slate.csv
```

`--second-guess-pool allowed` lets second guesses use any allowed guess and is the default.

`--second-guess-pool answers` limits second guesses to possible answer words.

Feedback symbols are:

- `G` = green
- `Y` = yellow
- `.` = gray

## Compare Fixed Strategies

Treat `slate` as a fixed baseline opener:

```bash
python -m src.wordle_lab --strategy baseline --first slate
python -m src.wordle_lab --strategy second-map --first slate --second-guess-pool answers
python -m src.wordle_lab --strategy second-map-trap --first slate --second-guess-pool answers --show-worst 25
python -m src.wordle_lab --strategy second-map-bucket --first slate --second-guess-pool answers --show-worst 25
python -m src.wordle_lab --strategy second-map-expected --first slate --second-guess-pool answers --endgame-threshold 10
python -m src.wordle_lab --strategy second-map-hybrid --first slate --second-guess-pool answers --trap-threshold 3
python -m src.wordle_lab --strategy second-map --first slate --second-guess-pool answers --show-worst 25
python -m src.wordle_lab --strategy second-map-bucket --first slate --second-guess-pool answers --worst-patterns 20
python -m src.wordle_lab --strategy second-map-bucket --first slate --second-guess-pool answers --answer-weighting simple
python -m src.wordle_lab --tune-pattern slate ....Y --strategy second-map-bucket --second-guess-pool answers --top 25
python -m src.wordle_lab --tune-pattern slate ....Y --strategy second-map-bucket --second-guess-pool answers --top 25 --branch-summary
python -m src.wordle_lab --tune-pattern slate ....Y --strategy second-map-bucket --second-guess-pool answers --second rocky --show-worst 25
python -m src.wordle_lab --tune-branch slate ....Y rocky Y.... --strategy second-map-bucket --second-guess-pool answers --top 25
python -m src.wordle_lab --tune-path slate ....Y rocky Y.... fiend ..Y.. --strategy second-map-bucket --second-guess-pool answers --top 25
python -m src.wordle_lab --strategy second-map --first slate --second-guess-pool answers --csv results/strategy_slate.csv
python -m src.wordle_lab --compare-strategies --csv results/strategy_leaderboard.csv
```

`baseline` uses the normal solver after the first guess.

`second-map` uses the precomputed balanced second guess for the first feedback pattern, then continues with the normal solver.

`second-map-trap` starts the same way, then uses a probe guess when the remaining candidates look like a trap family, such as answers that share four fixed positions.

`second-map-bucket` starts the same way, then chooses later guesses by minimizing the largest feedback bucket among the remaining candidates. This catches broader trap families that do not share exactly four fixed positions.

`second-map-expected` starts like `second-map-bucket`, then uses the bucket strategy above `--endgame-threshold` and a guarded memoized expected-value search at or below that candidate count. The default threshold is 10.

`second-map-hybrid` uses the normal candidate guess unless it would leave a feedback bucket larger than `--trap-threshold`; then it switches to the bucket probe. The default threshold is 2.

Use `--show-worst N` to print the hardest solved games after the strategy summary. When `--csv` is also used, Wordle Lab writes a companion worst-games CSV next to the strategy CSV with `_worst` added to the file name.

Use `--worst-patterns` to group solved games by the first feedback pattern and rank the hardest patterns by risk. Pass a number, such as `--worst-patterns 20`, to limit the table.

Use `--recommend` to get a next-guess recommendation from a partial game state. The state is alternating guess/feedback pairs, and the recommendation uses the selected strategy's normal decision logic, including tuned overrides unless `--no-overrides` is supplied:

```bash
python -m src.wordle_lab \
  --recommend \
  --strategy second-map-bucket \
  --second-guess-pool answers \
  --state slate ....Y
```

For daily play, the friendly shortcuts use the full word lists and answer-only `second-map-bucket` recommendations:

```bash
python -m src.wordle_lab --pure-recommend slate ....Y
python -m src.wordle_lab --human-recommend slate ....Y
python -m src.wordle_lab --human-recommend slate ....Y drown .Y...
```

`--human-recommend` also uses `data/prior_answers_dated.csv`, `--prior-policy downweight`, and `--recommend-top 10` by default. It uses the latest date in the dated prior file unless `--as-of-date YYYY-MM-DD` is supplied. `--pure-recommend` uses the same full word lists without prior weighting. Both shortcuts allow `--recommend-top N`.

Use `--recommend-top N` to show ranked alternatives. The first row matches the recommended next guess and each row shows whether the guess is an answer or probe, its largest feedback bucket, bucket count, expected remaining candidates, and weighted expected remaining when Human Mode downweighting is active.

Human Mode overrides are selected by downstream weighted simulation, so an override may not always have the best immediate max bucket or immediate expected-remaining score in the alternatives table.

Human Mode recommendations use dated prior-answer weights when provided:

```bash
python -m src.wordle_lab \
  --recommend \
  --strategy second-map-bucket \
  --second-guess-pool answers \
  --state slate ....Y drown .Y... \
  --recommend-top 10 \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --as-of-date 2026-05-28
```

The recommendation report shows the remaining candidate count, top candidates, prior weights, recommended guess, whether it is an answer or probe, bucket summary, and a short explanation.

Use `--tune-pattern FIRST PATTERN` to focus on one first-feedback bucket and rank possible second guesses. The ranking prefers lower risk, then lower average guesses, then more solves in four or fewer guesses. Add `--csv` to save the tuning table.

Long `--tune-pattern` runs print progress while evaluating second guesses:

```text
Pattern .....: evaluated 100/2315 second guesses; current best frond risk 12; elapsed 42.10s
```

Use these options for faster tuning passes before running an exhaustive search:

```bash
python -m src.wordle_lab \
  --tune-pattern slate ..... \
  --strategy second-map-bucket \
  --second-guess-pool answers \
  --second-guess-candidates top \
  --max-second-guesses 100 \
  --top 25
```

`--second-guess-candidates all` preserves exhaustive behavior and is the default.

`--second-guess-candidates top` uses the same deterministic pre-ranked subset used by `--build-second-map`.

`--max-second-guesses N` limits how many second guesses are evaluated for the pattern.

When `--csv` is supplied for `--tune-pattern`, rows are written incrementally as each second guess is evaluated, so interrupted long runs still leave useful partial output.

Add `--branch-summary` to tune-pattern output to show whether each second guess creates an ugly second-feedback branch.

Add `--second WORD` to evaluate one second guess for that pattern. Pair it with `--show-worst N` or `--show-pattern-worst N` to inspect the hardest answers inside that first-feedback bucket.

Use `--tune-branch FIRST FIRST_PATTERN SECOND SECOND_PATTERN` to tune third guesses for one exact branch after the first two guesses. Add `--second WORD` to inspect one specific third guess and pair it with `--show-worst N` for the hardest games in that branch.

Use `--tune-path` for deeper branches. Give alternating guess/pattern pairs ending with the latest feedback pattern, and Wordle Lab will tune the next guess from that position. Add `--branch-summary` to show the worst next-feedback branch for each candidate next guess.

Use `--answer-weighting simple` to prefer more Wordle-like answer candidates when the strategy is choosing among remaining possible answers. The default is `--answer-weighting off`, which preserves the original first-remaining-candidate behavior.

Built-in pattern and path overrides are tuned for `second-map-bucket`. They apply by default only to `second-map-bucket`, so baseline, second-map, trap, and hybrid comparisons stay untuned unless code explicitly opts in. Use `--no-overrides` with `second-map-bucket` to compare against the unmodified second-map recommendation.

`--final-cluster-overrides on` is experimental. Exact final-cluster overrides can reduce 5-guess games but may introduce 6-guess games. For the current uniform full-list benchmark, the recommended champion strategy keeps `--final-cluster-overrides off`, which is also the default.

Use `--compare-strategies` to run the built-in `slate` leaderboard across baseline, second-map, trap, and bucket strategies with both answer-only and allowed second-guess pools.

## Pure Mode And Human Mode

Wordle Lab can be used in two broad ways:

- **Pure Mode** treats every answer in the answer list as equally likely. This is best for strategy research, regression testing, and apples-to-apples benchmarks.
- **Human Mode** uses prior-answer history to model real Wordle play. It can exclude or downweight words that have already appeared.

The current champion results are summarized near the top; this section explains the modes and commands.

The current Pure Mode benchmark champion is:

```text
strategy: second-map-bucket
first guess: slate
second-guess-pool: answers
average: 3.47
5s: 39
6s: 0
risk: 78
```

Human Mode uses these local prior-answer files:

- `data/prior_answers.txt`
- `data/prior_answers_dated.csv`

`data/prior_answers.txt` is a plain word list, one lowercase five-letter answer per line.

`data/prior_answers_dated.csv` has two columns:

```csv
date,word
2025-08-31,petal
2021-06-19,cigar
```

### Prior Answer Commands

Show plain prior-answer stats:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --prior-answers data/prior_answers.txt \
  --prior-stats
```

Show dated prior-answer stats:

```bash
python -m src.wordle_lab \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-dated-stats
```

Show prior weight buckets for the configured answer list:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --prior-answers-dated data/prior_answers_dated.csv \
  --as-of-date 2026-05-28 \
  --prior-weight-stats
```

These commands also have project defaults, but the explicit paths above match the full-list Human Mode workflow.

Clean a pasted or downloaded historical answer source into `data/prior_answers.txt`:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --clean-prior-source downloads/past_wordle_answers_raw.txt data/prior_answers.txt
```

The cleaner extracts lowercase five-letter alphabetic words, deduplicates them in first-seen order, keeps only words from the configured answer list, and writes one word per line.

### Prior Policies

Use `--prior-policy` to choose how prior answers affect solving:

- `ignore` keeps current behavior. Prior answers are loaded for stats only.
- `exclude` removes prior answers from tested targets and solution candidates, while still allowing them as guesses/probes.
- `downweight` keeps prior answers possible, but prefers less-recent or never-used answers in small endgame choices.

`exclude` is mostly diagnostic because modern Wordle can reuse answers. For real-world Human Mode, prefer `--prior-policy downweight`.

### Prior Weight Buckets

When `--prior-policy downweight` is used with `--prior-answers-dated`, each tested answer gets a deterministic weight. The default `--prior-weight-preset current` schedule is:

```text
never used:               1.00
used within last 90 days: 0.05
used 91-365 days ago:    0.15
used 366-730 days ago:   0.35
used more than 730 days:  0.60
```

Other presets let you model different attitudes toward repeats:

```text
preset           0-90  91-365  366-730  730+  never
current          0.05  0.15    0.35     0.60  1.00
conservative     0.10  0.25    0.50     0.75  1.00
aggressive       0.02  0.10    0.25     0.50  1.00
repeat-friendly  0.15  0.35    0.60     0.85  1.00
```

You can also provide a one-off custom schedule:

```bash
python -m src.wordle_lab \
  --strategy second-map-bucket \
  --first slate \
  --second-guess-pool answers \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --prior-weight-values 0.005,0.05,0.15,0.35 \
  --as-of-date 2026-05-28 \
  --show-weighted-score
```

`--prior-weight-values W90,W365,W730,WOLD` means `0-90 days`, `91-365 days`, `366-730 days`, and `730+ days`; never-used answers always keep weight `1.00`. Values must be monotonic: `0 <= W90 <= W365 <= W730 <= WOLD <= 1.00`. If both `--prior-weight-preset` and `--prior-weight-values` are supplied, the custom values win and reports label the schedule as `custom`.

The date basis comes from `--as-of-date YYYY-MM-DD`. If no date is provided, Wordle Lab uses the latest date in the dated prior file, or today when the file is empty.

To compare the Human Mode weighted benchmark under every preset:

```bash
python -m src.wordle_lab \
  --compare-prior-weight-presets \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --strategy second-map-bucket \
  --first slate \
  --second-guess-pool answers \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --as-of-date 2026-05-28
```

The comparison reports total weight, weighted average, weighted `<=3`, weighted `<=4`, weighted `5s`, weighted `6s`, weighted failures, and weighted risk for each preset. Weighted averages print with four decimal places by default; use `--precision N` to choose a different number of decimal places for report averages.

To grid-search custom Human Mode recency schedules:

```bash
python -m src.wordle_lab \
  --search-prior-weight-schedules \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --strategy second-map-bucket \
  --first slate \
  --second-guess-pool answers \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --decision-weight-preset aggressive \
  --as-of-date 2026-05-28 \
  --weight-90 0.01,0.02,0.05,0.08,0.10 \
  --weight-365 0.08,0.10,0.12,0.15,0.20 \
  --weight-730 0.20,0.25,0.30,0.35 \
  --weight-old 0.45,0.50,0.55,0.60 \
  --top 25 \
  --csv results/prior_weight_schedule_search.csv
```

The search only evaluates monotonic schedules where `weight_90 <= weight_365 <= weight_730 <= weight_old <= 1.00`. It prints the top rows and saves all evaluated schedules when `--csv` is supplied.

Schedule search is fast because it runs the selected strategy once, caches each answer's result and prior-age bucket, then scores weight schedules against those fixed decisions. The CSV is created immediately, each scored schedule is flushed as it is written, and interrupted runs resume from existing rows unless `--force` is supplied. Use `--decision-weight-preset PRESET` to choose the prior-weight preset used for the one actual strategy run; by default it uses the active prior-weight schedule, including `--prior-weight-values` when supplied. Promising schedules should be confirmed with a full Human Mode scoreboard because schedule search does not retune decisions for every schedule:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --strategy second-map-bucket \
  --first slate \
  --second-guess-pool answers \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --prior-weight-values 0.005,0.05,0.15,0.35 \
  --as-of-date 2026-05-28 \
  --show-weighted-score \
  --weighted-worst-patterns 25
```

### Weighted Human-Mode Scoring

Pure Mode reports the normal uniform benchmark score. Human Mode can also report a weighted score:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --strategy second-map-bucket \
  --first slate \
  --second-guess-pool answers \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --as-of-date 2026-05-28 \
  --show-weighted-score
```

The weighted average is:

```text
sum(prior_weight * guesses) / sum(prior_weight)
```

The report also includes weighted `<=3`, `<=4`, `5s`, `6s`, and failed totals.

To inspect choices changed by dated prior weighting:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --strategy second-map-bucket \
  --first slate \
  --second-guess-pool answers \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --as-of-date 2026-05-28 \
  --show-prior-weighting-changes
```

This diagnostic prints the normal guess, weighted guess, remaining candidates, prior weights, answer, and guess number for changed decisions.

To find the first-feedback patterns that are worst under weighted Human Mode risk:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --strategy second-map-bucket \
  --first slate \
  --second-guess-pool answers \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --as-of-date 2026-05-28 \
  --show-weighted-score \
  --weighted-worst-patterns 25
```

`--weighted-worst-patterns` keeps the normal `--worst-patterns` report unchanged. It groups games by first-guess feedback pattern and ranks them by weighted Human Mode risk, using weighted 5s, weighted 6s, and weighted failures.

For Human Mode tuning, `--tune-pattern` also supports a weighted objective:

```bash
python -m src.wordle_lab \
  --answers data/wordle_answers_full.txt \
  --allowed data/wordle_allowed_guesses_full.txt \
  --tune-pattern slate ....Y \
  --strategy second-map-bucket \
  --second-guess-pool answers \
  --prior-answers-dated data/prior_answers_dated.csv \
  --prior-policy downweight \
  --as-of-date 2026-05-28 \
  --tune-pattern-objective weighted-risk \
  --top 25
```

`weighted-risk` is only for `--tune-pattern` with dated prior answers and `--prior-policy downweight`. It ranks second guesses by fewer weighted 6s, lower weighted risk, fewer weighted 5s, lower weighted average, then the normal 6s/risk tie-breakers. When `--show-weighted-score` or `--tune-pattern-objective weighted-risk` is used with `--tune-pattern`, the table includes `weighted_avg`, `weighted_5s`, `weighted_6s`, and `weighted_risk`.

Human Mode can also use different tuned pattern overrides from Pure Mode. For example, Pure Mode keeps the `slate` / `....Y` / `answers` override at `rocky`, while Human Mode with `--prior-policy downweight` and dated prior answers uses `drown` for that same first-feedback pattern. Human Mode also uses `hound` for `..YY.` and `began` for `..Y.Y`, while Pure Mode keeps `pouch` and `march`. Use `--no-overrides` to disable both Pure Mode and Human Mode overrides.

## Word Lists

The starter word lists in `data/` are tiny so the project stays easy to inspect.

- `data/answers.txt` contains possible answer words.
- `data/allowed_guesses.txt` contains allowed guesses.

Add more five-letter lowercase words, one word per line, to run larger experiments.

## Run Tests

From the project folder:

```bash
python -m unittest discover
```
