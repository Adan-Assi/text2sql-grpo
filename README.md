# text2sql-grpo

> **Status: work in progress (documentation stage).** Nothing in this repository has been trained or evaluated yet. All results below are placeholders. Progress is tracked in [docs/ROADMAP.md](docs/ROADMAP.md).

Fine-tune a small open language model to write SQLite queries from a natural-language question and a database schema, using **reinforcement learning with an execution-based reward**: a generated query is rewarded for *returning the right rows when it is run*, not for matching a reference string.

The training runs through [`intuit/foresight-rl-core`](https://github.com/intuit/foresight-rl-core), an open-source, YAML-driven framework for RL fine-tuning of LLMs, using its local GRPO backend. Plain Hugging Face TRL is the planned fallback if the framework turns out to be impractical (see [docs/DECISIONS.md](docs/DECISIONS.md)).

## Documentation conventions

Every technical claim in this repo's docs is one of:

| Tag | Meaning |
|---|---|
| `[VERIFIED]` | Read directly from a primary source (docs, dataset card, config) or observed in a run. The source is named. |
| `[PROPOSED]` | A plan or design choice that has not been validated. May change. |
| `[OPEN]` | An unanswered question. Listed in [docs/DECISIONS.md](docs/DECISIONS.md). |

## Motivation

- **Learning goal.** Get hands-on experience with an RL fine-tuning pipeline: reward design, rollouts, training dynamics, and evaluation, rather than only reading about them.
- **A natural verifier.** SQL is unusually well suited to RL: you can run a query and check the answer, with no human labels and no LLM judge at training time.
- **Why not only supervised fine-tuning?** Many different SQL strings answer the same question. Training on one gold string penalizes valid alternatives. An execution-based reward accepts any query that returns the right result. (This is the project's working hypothesis; it is not tested here.)

## The problem: Text-to-SQL

Given a question and a schema, produce a query.

```
Question: What is the total number of hospital beds in each state?
Schema:   CREATE TABLE Beds (State VARCHAR(50), Beds INT);
Gold SQL: SELECT State, SUM(Beds) FROM Beds GROUP BY State;
```

The model must pick the right tables and columns, aggregation, grouping, and filters, and emit syntactically valid SQL. Background: [docs/CONCEPTS.md](docs/CONCEPTS.md).

## Approach

```
 HF dataset ──► data prep ──► train.jsonl / eval.jsonl
 (question,        │          row: prompt, db_context (schema + data), gold_result
  schema, SQL)     │
                   ▼
   ┌──────────────── GRPO training (foresight-rl-core → TRL) ─────────────────┐
   │ 1. take a batch of prompts                                               │
   │ 2. model (Qwen3 + LoRA) samples K SQL attempts per prompt   (rollouts)   │
   │ 3. reward function scores each attempt  ◄── executor: run SQL in SQLite  │
   │ 4. compute each attempt's advantage relative to its group                │
   │ 5. update LoRA weights toward above-average attempts                     │
   └──────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
          LoRA adapter ──► evaluation script (held-out prompts, greedy decoding)
                           base model vs tuned model → execution accuracy
```

The reward function never compares SQL text. It builds an in-memory SQLite database from the example's schema and data, runs the model's query, and compares the returned rows to a precomputed gold result.

## Components

| Component | Current choice | Status |
|---|---|---|
| Model | Qwen3-1.7B, thinking disabled; Qwen3-0.6B as fallback | `[PROPOSED]` |
| Adaptation | LoRA | `[PROPOSED]` |
| RL algorithm | GRPO via foresight-rl-core local backend (built on TRL's `GRPOTrainer`); TRL directly as fallback | Backend `[VERIFIED]` in docs; fit for this project `[OPEN]` |
| Execution engine | SQLite (Python standard-library `sqlite3`), in-memory, sandboxed | `[PROPOSED]` |
| Reward | Execution-based, tiered (details below) | `[PROPOSED]` |
| Dataset | `gretelai/synthetic_text_to_sql` (Apache-2.0) | `[PROPOSED]` |
| Evaluation | Execution accuracy on held-out examples, base vs tuned | `[PROPOSED]` |
| Hardware | Rented single GPU (24 GB class targeted); no GPU needed until Phase 4 | `[PROPOSED]`, memory fit unverified |

### Model: Qwen3

Qwen3 is the model family the framework's local-GPU recipe targets (the `qwen3` recipe is documented for "Qwen3-14B and similar") `[VERIFIED]`. We plan a much smaller member so that it fits one rented GPU `[PROPOSED]`. Qwen3 has a "thinking" mode; the framework exposes `model.enable_thinking` (default `true`) `[VERIFIED]`. SQL answers are short, so we plan to disable it `[PROPOSED]`.

### LoRA

Instead of updating all weights, LoRA trains small low-rank matrices added to selected layers. This cuts memory and produces a small adapter file. The framework exposes `model.lora` with `r`, `alpha`, `dropout`, and `target_modules` `[VERIFIED]`. Our values are `[OPEN]`.

### GRPO

For each prompt the model samples a group of K answers, each is scored, and each answer's advantage is its score relative to the group. No separate value network is needed. Variants and parameters are covered in [docs/CONCEPTS.md](docs/CONCEPTS.md); the K and normalization choices are `[OPEN]` in [docs/DECISIONS.md](docs/DECISIONS.md).

### SQLite and the execution-based reward

Proposed reward structure `[PROPOSED]`, values not yet chosen:

1. Output has no extractable SQL, fails to run, or times out: lowest reward.
2. Runs without error: small reward.
3. Result set matches the gold result: full reward.
4. Optional small penalty for degenerate or overlong outputs.

Model-generated SQL is untrusted input, so execution is planned inside a read-only, in-memory database with a time limit and restricted statements `[PROPOSED]`.

### Dataset

`gretelai/synthetic_text_to_sql`: Apache-2.0 license; fields include `sql_prompt`, `sql_context` (CREATE TABLE and INSERT statements), `sql`, `sql_complexity`, `sql_task_type`, and `domain` `[VERIFIED from the dataset card]`. Because `sql_context` contains data, queries can actually be executed. Open points to settle in Phase 1: split sizes, which task types to keep (the dataset also covers non-SELECT tasks), and how many gold queries run cleanly in SQLite `[OPEN]`.

### Evaluation

Primary metric: **execution accuracy** on a held-out set never used in training, with the same prompt template, executor, and decoding settings for the base and tuned models `[PROPOSED]`. Optional secondary check on a different-schema benchmark such as Spider dev `[PROPOSED]`. Details and statistical caveats: [docs/DECISIONS.md](docs/DECISIONS.md).

## Compute and cost

Phases 0–3 run on a laptop with no GPU. A GPU is only needed from Phase 4 onward, and the plan is to rent one by the hour, script the setup, copy results off, and terminate it `[PROPOSED]`. Provider, instance, and budget are `[OPEN]`.

## Project layout (planned)

```
text2sql-grpo/
├── README.md
├── docs/                   CONCEPTS, ROADMAP, DECISIONS, EXPERIMENT_LOG
├── src/sqlgrpo/            executor, reward, data prep         (Phases 1–2)
├── tasks/                  foresight-rl-core task module        (Phase 3)
├── configs/                YAML run configs                     (Phase 3+)
├── scripts/                data build, baseline and final eval  (Phases 1, 4, 7)
├── tests/                  unit tests for executor and reward
├── data/                   generated data (git-ignored)
└── third_party/
    └── foresight-rl-core/  clone of the framework (git-ignored)
```

Package and folder names are provisional; see decision D-020.

## Installation and reproduction

> Placeholders. Fill in each step only after it has been run successfully and recorded in [docs/EXPERIMENT_LOG.md](docs/EXPERIMENT_LOG.md).

| Pin | Value |
|---|---|
| Python | `TODO` (3.12 proposed) |
| foresight-rl-core commit | `TODO` (record with `git rev-parse HEAD` in Phase 0) |
| GPU-machine dependencies | `TODO` (generated by `rl-train setup-local-gpu --recipe qwen3`; resulting versions to be recorded) |
| Base model revision | `TODO` |
| Dataset revision | `TODO` |

1. **Local setup (laptop):** `TODO` (Phase 0)
2. **Build the dataset:** `TODO` (Phase 1)
3. **Run tests:** `TODO` (Phase 2)
4. **GPU setup:** `TODO` (Phase 4)
5. **Baseline evaluation:** `TODO` (Phase 4)
6. **Train:** `TODO` (Phases 5–6)
7. **Evaluate the tuned model:** `TODO` (Phase 7)

## Results

> No results yet. This table will be filled from [docs/EXPERIMENT_LOG.md](docs/EXPERIMENT_LOG.md) in Phase 7–8.

| Model | Held-out execution accuracy | Valid-SQL rate | Notes |
|---|---|---|---|
| Base (zero-shot) | — | — | |
| After GRPO | — | — | |

## Limitations

Anticipated from the design, to be updated with real findings:

- **Synthetic data.** Training and primary evaluation data are LLM-generated, so results may not transfer to real-world schemas and questions.
- **Execution accuracy can give false positives.** A wrong query can return the same rows as the gold query by coincidence, especially on small tables or empty results.
- **One SQL dialect.** SQLite only; syntax and function support differ from PostgreSQL and MySQL.
- **Small scale.** A small model, a short training run, and likely a single seed, so small differences will not be statistically meaningful.
- **Reward hacking is possible.** Any proxy reward can be gamed. How we check for this will be documented.
- **Young framework.** foresight-rl-core is new and its documentation is aimed partly at Intuit's own infrastructure `[VERIFIED: single commit, 8 stars, 0 forks, PRs restricted to collaborators when inspected on 2026-11-15]`.

## Future work

Ideas, not commitments: a reward ablation (binary vs tiered), a K ablation, multiple seeds, a harder out-of-distribution benchmark, a supervised-fine-tuning baseline run outside the framework, a PostgreSQL-dialect variant, and a multi-criteria reward modeled on the framework's paper.

## Documentation

| File | Purpose |
|---|---|
| [docs/CONCEPTS.md](docs/CONCEPTS.md) | Background concepts, explained for newcomers |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phases, status, deliverables, verification criteria |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision records, evidence base, open questions |
| [docs/EXPERIMENT_LOG.md](docs/EXPERIMENT_LOG.md) | Template and index for experiment records |

## Acknowledgements

- [`intuit/foresight-rl-core`](https://github.com/intuit/foresight-rl-core) and its accompanying paper (arXiv 2608.11787).
- [`gretelai/synthetic_text_to_sql`](https://huggingface.co/datasets/gretelai/synthetic_text_to_sql) (Apache-2.0).
- Qwen3 models; Hugging Face TRL, vLLM, and DeepSpeed.

## License

`TODO`: choose a license for this repository. Check the licenses of foresight-rl-core, the base model, and any datasets before publishing derived artifacts (for example, a LoRA adapter).

## Dependencies

- **Foresight RL Core:** https://github.com/intuit/foresight-rl-core
- **Pinned commit:** `705d8e40ee57ff91f4461cca5fb5303981123db1`
