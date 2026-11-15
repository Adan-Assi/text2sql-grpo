# Decisions

Last updated: 2026-11-15

This file records what has been decided, why, what else was considered, and what is still unknown. It is the single place for project-specific choices. Concept explanations are in [CONCEPTS.md](CONCEPTS.md); phase status is in [ROADMAP.md](ROADMAP.md).

## Status definitions

| Status | Meaning |
|---|---|
| **CONFIRMED** | Explicitly agreed by the project owner, or a fact forced by verified documentation |
| **PROVISIONAL** | A reasoned starting choice, agreed as the plan but not validated by any run. May change. |
| **OPEN** | Not decided. Candidate options may be listed, with or without a leaning. |

When a decision changes, edit the record, add a line under **History**, and keep the old reasoning visible.

## Index

| ID | Decision | Status | Resolve in |
|---|---|---|---|
| D-001 | Project: Text-to-SQL with execution-based reward | CONFIRMED | n/a |
| D-002 | Training path: foresight-rl-core local GRPO, TRL as fallback | CONFIRMED (strategy); fallback trigger in D-022 | Phase 0 / 4 |
| D-003 | Own repo; framework cloned to `third_party/`; task loaded by file path | PROVISIONAL | Phase 0 / 3 |
| D-004 | Dataset: `gretelai/synthetic_text_to_sql` | PROVISIONAL | Phase 1 |
| D-005 | Reward is based on executing SQL in SQLite | CONFIRMED | n/a |
| D-006 | Reward tiers, values, and result-comparison rules | OPEN (tier shape PROVISIONAL) | Phase 2 |
| D-007 | Model: Qwen3-1.7B, fallback Qwen3-0.6B | PROVISIONAL | Phase 4 |
| D-008 | Disable Qwen3 thinking mode | PROVISIONAL | Phase 3 / 4 |
| D-009 | GPU class and provider | PROVISIONAL (class) / OPEN (provider) | Phase 4 |
| D-010 | `vllm_mode` on one GPU: start with `none` | PROVISIONAL | Phase 4 |
| D-011 | K (`num_generations`) = 8 as starting value | PROVISIONAL | Phase 4–5 |
| D-012 | Reward normalization and loss type | OPEN | Phase 5 |
| D-013 | Select training prompts by base-model pass rate | PROVISIONAL | Phase 4 |
| D-014 | Evaluation protocol and eval set | PROVISIONAL | Phase 1 / 7 |
| D-015 | Baseline = untuned model, no SFT baseline | PROVISIONAL | Phase 4 |
| D-016 | Sandboxed SQL execution design | PROVISIONAL | Phase 2 |
| D-017 | What the prompt shows: schema only or schema plus data | OPEN | Phase 1 |
| D-018 | Python 3.12 + `uv`; laptop gets base package only | PROVISIONAL | Phase 0 |
| D-019 | Make our package installable | PROVISIONAL | Phase 1–3 |
| D-020 | Naming: `text2sql-grpo` vs skeleton names | OPEN | Phase 0 |
| D-021 | DeepSpeed ZeRO-2 on a single GPU | OPEN | Phase 0 / 4 |
| D-022 | Fallback trigger to plain TRL | PROVISIONAL | Gate G2 |
| D-023 | LoRA settings | OPEN | Phase 3 |
| D-024 | Scope exclusions | PROVISIONAL | n/a |

---

## Evidence base

### Verified facts

Sources read on 2026-11-15 unless noted. "Doc" means a file in the foresight-rl-core repository.

| # | Fact | Source |
|---|---|---|
| V1 | The framework is YAML-config driven; tasks supply reward functions, callbacks, and a dataset loader. | Repo landing page; `docs/tasks/creating-a-task.md` |
| V2 | A task module exports `get_reward_function(task_config)`, `get_callbacks(task_config)`, `get_dataset_loader(task_config, model_name)`. | `docs/tasks/creating-a-task.md` |
| V3 | Reward functions must be compatible with TRL's `GRPOTrainer` and have the form `fn(completions, **kwargs) -> list[float]`. Each extra dataset column arrives as a list with one entry per completion. `completions` may be `list[str]` or `list[list[dict]]`. | same |
| V4 | `task.type` resolves in order: file path (absolute, or ending `.py`), dotted Python path, built-in `foresightrlcore.tasks.<name>`. | same |
| V5 | The docs recommend implementing a `mock` reward mode for smoke tests; reward functions can be tested without a GPU. | same |
| V6 | Dataset format: JSONL, each record has `prompt` (string or list of chat messages); extra columns become reward kwargs. The docs' example loader reads `*.jsonl` from a directory and applies the chat template with `enable_thinking`. | `docs/launching-local-job.md`; `docs/tasks/creating-a-task.md`; sample `email_outcome/train.jsonl` |
| V7 | Local backend: `execution.type: local` with `execution.local.gpus` required. `infra.vllm_mode` is `server`, `colocate`, or `none`. In `server` mode GPU count must be ≥ `vllm_gpu_count + training_gpu_count`. `none` uses `torchrun` with native HF generation and is described as suited to small models and fast iteration. `colocate` is described as for memory-constrained setups. | `docs/launching-local-job.md` |
| V8 | GPU dependencies are installed on the GPU machine with `rl-train setup-local-gpu --recipe <name>`, then `pip install -r local-requirements.txt`. The `qwen3` recipe pins `torch >=2.6`, `trl[vllm] >=0.28`, `transformers >=4.57` ("Qwen3-14B and similar"). Quick Start says to run these steps on the GPU machine. | same |
| V9 | Documented training defaults include `per_device_batch_size: 4`, `gradient_accumulation_steps: 2`, `learning_rate: 5e-5`, `bf16: true`, `gradient_checkpointing: true`, `deepspeed: ds_zero2_config.json`, `report_to: tensorboard`, `max_steps` override for smoke tests. | same (defaults table) |
| V10 | The docs' example GRPO block (from the `advice` task example, not stated as defaults) uses `num_generations: 8`, `max_completion_length: 8192`, `beta: 0.001`, `epsilon: 0.2`, `epsilon_high: 0.28`, `loss_type: dr_grpo`, `scale_rewards: false`, `temperature: 0.6`, `top_p: 0.95`, `top_k: 20`. | same |
| V11 | Model config: `enable_thinking` default `true`; LoRA defaults `r: 32`, `alpha: 64`, `dropout: 0.05`, Qwen-style `target_modules`. | same |
| V12 | The local backend writes output to `output.s3_path` (a local path is allowed). `environment` and `secrets` sections are not required by the shipped examples, which "do not require a `secrets:` block". | same; `examples/configs/README.md` |
| V13 | `local_example.yaml` is described as GRPO on one local GPU (GPU 0), has no placeholders, and reads `examples/datasets/email_outcome/train.jsonl` when run from the repo root. `validate` is purely static and needs no GPU or AWS access. | `examples/configs/README.md`; `docs/launching-local-job.md` |
| V14 | There is no dedicated GRPO smoke-test config. The only SFT smoke tests use `sft_verl` on `ml.p4d.24xlarge`. The documented GRPO smoke-test pattern is `training.max_steps: 10` plus mock reward mode. | `examples/smoke_tests/README.md`; `docs/launching-local-job.md` |
| V15 | The built-in `advice` task's LLM judge uses Intuit's Genos client by default; a Bedrock provider is documented as an alternative. | `docs/launching-local-job.md`; `docs/tasks/creating-a-task.md` |
| V16 | The local-backend doc says it "supports the same methods as SageMaker Training Jobs"; the config template comments list `grpo`, `sft`, `dpo`. | `docs/launching-local-job.md` |
| V17 | Repo state when inspected: single commit, 8 stars, 0 forks; pull requests restricted to collaborators. | Repo landing page (2026-11-15) |
| V18 | Dataset `gretelai/synthetic_text_to_sql`: Apache-2.0; fields include `sql_prompt`, `sql_context` (CREATE TABLE and INSERT statements), `sql`, `sql_complexity`, `sql_task_type`, `domain`, `sql_explanation`; task types include non-SELECT tasks. | Hugging Face dataset card |
| V19 | Python 3.10+ is required (docs); `uv` is the recommended installer (README, read earlier). The README's stated upper version bound should be re-checked in Phase 0. | `docs/launching-local-job.md`; README |

### Not yet verified

| # | Item | Why it matters |
|---|---|---|
| U1 | Contents of `local_example.yaml` (model, `vllm_mode`, batch sizes, `max_steps`, task) | Template for our config; decides whether running it first is cheap |
| U2 | Source of the shipped `outcome_category` task | Working example of the loader (file vs directory) and reward conventions |
| U3 | `LOCAL_GPU_RECIPES` and `setup-local-gpu --list` output; exact resolved versions | Whether Qwen3-1.7B fits the pinned stack |
| U4 | Location and single-GPU behavior of `ds_zero2_config.json` | D-021 |
| U5 | The full GRPO parameter reference (`docs/launching-sagemaker-training-job.md`) | True defaults for K, normalization, loss type |
| U6 | Which methods actually run on one local GPU (V16) | Only relevant if scope expands |
| U7 | TRL batch semantics for `per_device_batch_size`, `gradient_accumulation_steps`, `num_generations` | D-011 |
| U8 | Whether the base install pulls in torch | Laptop setup size |
| U9 | The user's OS and whether a local GPU exists | Phase 0 commands; local baseline feasibility |
| U10 | Dataset split sizes; fraction of gold queries that run in SQLite | D-004, D-014 |
| U11 | Peak GPU memory, time per step, and cost for our setup | D-007, D-009 |
| U12 | Licenses of foresight-rl-core, Qwen3 weights, derived adapters | Phase 8 |
| U13 | Phase 0 command results | Gate G1 |

---

## Decision records

### D-001: Project choice
**Status:** CONFIRMED.
**Decision.** Build a Text-to-SQL model trained with an execution-based reward.
**Why.** Fits the owner's interests and skills (SQL, NLP, RL); the reward is deterministic, cheap, and needs no LLM judge (V15 shows judge-based rewards need extra setup and cost); results are measurable before/after.
**Alternatives considered.** Strict-JSON extraction from financial documents; instruction-constraint following with verifiers (IFEval-style); Countdown/GSM8K reasoning. Not chosen: weaker "why RL" argument, more reward-hacking surface and code, or less distinctive, respectively.

### D-002: Training path
**Status:** CONFIRMED (strategy); the switch condition is D-022.
**Decision.** Use foresight-rl-core's local GRPO backend as the primary path. Fall back to plain TRL `GRPOTrainer` with the same reward function if the framework is impractical.
**Why.** The owner wants hands-on experience with the framework; the reward signature is TRL-compatible (V3), so the fallback costs little.
**Alternatives.** Plain TRL from the start (fewer layers, but forgoes the project's purpose); SageMaker backend (cost, AWS setup, large instances in the docs).

### D-003: Repository structure
**Status:** PROVISIONAL.
**Decision.** Keep our code in its own repository. Clone the framework into `third_party/` (git-ignored), install it editable, and load our task via a `.py` file path (V4). Do not fork.
**Why.** Reproducibility (pin the commit); readable source and examples; PRs to upstream are restricted anyway (V17).
**Open.** Nothing has been run (U13). How relative paths and file-path tasks resolve inside the training subprocess is unverified.

### D-004: Dataset
**Status:** PROVISIONAL.
**Decision.** Use `gretelai/synthetic_text_to_sql`, keeping SELECT-type examples whose gold query executes in SQLite and returns a usable result.
**Why.** Apache-2.0 (V18); `sql_context` includes data, so execution-based rewards are possible; large enough for train/eval splits.
**Alternatives.** Spider (real multi-table schemas; databases need a separate download; better as an out-of-distribution test); BIRD (heavier); `b-mc2/sql-create-context` (no data, so no execution).
**Risks.** Synthetic data; some gold queries may not be valid SQLite; tables may be tiny, raising false-positive risk.
**Open.** U10.

### D-005: Execution-based reward on SQLite
**Status:** CONFIRMED.
**Decision.** Reward is computed by executing the generated query in SQLite and comparing results to a precomputed gold result.
**Why.** This is the project's premise and gives a deterministic, free verifier. The same executor serves training and evaluation.
**Alternatives.** String or AST match with gold SQL (penalizes valid alternatives); LLM judge (cost, nondeterminism, setup).

### D-006: Reward structure and result comparison
**Status:** OPEN (tier shape PROVISIONAL).
**Proposed shape.** Failure to extract/run/finish in time → lowest; runs without error → small credit; result matches gold → full credit; optional small penalty for degenerate or overlong outputs.
**Open.**
- Numeric values for each tier.
- Result comparison: unordered multiset vs ordered; when `ORDER BY` is present; column order and names; float tolerance; NULLs; duplicates.
- Treatment of examples with empty gold results (proposal: drop them, to reduce coincidental matches).
- Whether partial credit helps or invites shortcuts. Possible ablation: binary vs tiered reward.
**Revisit.** Phase 2 design; Phase 5 samples.

### D-007: Model size
**Status:** PROVISIONAL.
**Decision.** Qwen3-1.7B as the primary model; Qwen3-0.6B as fallback.
**Why.** Same family as the framework's `qwen3` recipe (V8); small enough that LoRA training plausibly fits a 24 GB GPU (estimate, U11).
**Alternatives.** Qwen3-0.6B only (cheaper; baseline may be too weak to give within-group variance); a larger Qwen3 (more memory, cost, and time); a code-specialized model from another family (recipe compatibility unverified).
**Risks.** The base model may already score too high or too low on the eval set; GRPO needs prompts that are sometimes solved and sometimes not (D-013). No run has validated the fit.
**Revisit.** After U1, U3 are read; after the Phase 4 baseline and memory measurements.

### D-008: Thinking mode
**Status:** PROVISIONAL.
**Decision.** Set `model.enable_thinking: false`.
**Why.** Default is `true` (V11); SQL answers are short; thinking would inflate completion length and cost.
**Open.** How the Qwen3 chat template and the loader interact when thinking is disabled; the reward should handle completions with or without `<think>` tags regardless (the framework ships `strip_thinking_tags`, per `docs/tasks/creating-a-task.md`).

### D-009: GPU and provider
**Status:** PROVISIONAL (class); OPEN (provider).
**Decision.** Target a single 24 GB-class NVIDIA GPU, rented by the hour, only from Phase 4. No GPU is needed for Phases 0–3.
**Why.** Estimate for a 1.7B model with LoRA, short completions, and one GPU (not measured, U11). `server` vLLM mode is impossible on one GPU (V7).
**Options for provider.**
- Hourly GPU marketplaces: no instance-quota step and per-minute billing, but variable reliability.
- AWS (for example g5 or g6 instances with 24 GB GPUs): consistent and good AWS practice, but new accounts often have zero quota for GPU instance families and must request an increase (general knowledge; not verified for this account).
- Avoid 16 GB cards without bf16 support unless `bf16` is changed (general knowledge; not verified for this stack).
**Cost.** Rough planning range of 10–25 GPU-hours total. Hourly prices vary and must be checked at rental time. No figure here is verified.
**Cost-control rules** `[PROPOSED]`. Develop and test on the laptop first; script the GPU setup; copy outputs off the machine; terminate (not just stop) instances after each session; set a billing alert.

### D-010: vLLM mode on one GPU
**Status:** PROVISIONAL.
**Decision.** Start with `vllm_mode: none` for the smoke test and first runs; consider `colocate` if generation speed is the bottleneck.
**Why.** `server` is not possible (V7); `none` has the fewest moving parts and is documented for small models.
**Open.** Whether `colocate` or `none` is practical with the default DeepSpeed config on one GPU (U4); speed of HF generation for K completions per prompt.

### D-011: K (`num_generations`)
**Status:** PROVISIONAL.
**Decision.** Start with K = 8.
**Why.** It is the value in the docs' example (V10, an example and not a recommendation). It gives enough completions per prompt to produce reward differences.
**Alternatives.** K = 4 (cheaper, noisier group statistics); K = 16 (better statistics, roughly double generation cost).
**Constraints and unknowns.** In TRL the generation batch size is expected to be divisible by K; the documented defaults (batch 4 × accumulation 2 = 8 on one GPU) would then mean one prompt per step. This reading of TRL is unverified (U7).
**Revisit.** After Phase 4 pass-rate data and Phase 5 curves. A K ablation is possible future work.

### D-012: Reward normalization and loss type
**Status:** OPEN.
**Candidates.**
- (a) Original GRPO advantage with division by group std.
- (b) No std scaling (`scale_rewards: false`) with `loss_type: dr_grpo`, as in the docs' example config (V10).
**Current leaning.** Start from the framework's example values (b), since the authors presumably exercised them, and revisit in Phase 5. This is a leaning, not a decision, and there is no evidence yet for either.
**Unknown.** The framework's actual defaults (U5); the precise definition of `dr_grpo` in the installed TRL version.
**Revisit.** After reading U5; possible short comparison in Phase 5 if budget allows.

### D-013: Training-prompt selection
**Status:** PROVISIONAL.
**Decision.** In Phase 4, sample K completions per training prompt from the base model, compute pass rates, and keep prompts that are sometimes but not always solved. The 20–70% band is a heuristic from the proposal, not a measured optimum.
**Why.** If all K completions get the same reward, advantages are zero (CONCEPTS §8).
**Rules.** Use the training split only; never the eval split.

### D-014: Evaluation protocol
**Status:** PROVISIONAL.
**Decision.**
- Primary: execution accuracy on a held-out set from the same dataset, built in Phase 1 and excluded from training. Size proposed at about 300.
- Same prompt template, executor, and greedy decoding for base and tuned models.
- Report valid-SQL rate alongside accuracy.
- Optional secondary: a different-schema benchmark such as Spider dev.
**Statistics.** The standard error of an accuracy near 50% on 300 examples is about 2.9 percentage points (√(0.25/300)). Differences within a few points should not be claimed as improvement. Comparing both models on the same examples allows a paired analysis.
**Distinct from.** The framework's in-training holdout (`data.eval_split_size`, default 100), which is not the final evaluation.
**Open.** Exact eval size; how the eval set is made reproducible when `data/` is git-ignored (for example, committing a list of example IDs plus the seed); whether to include Spider dev.

### D-015: Baseline
**Status:** PROVISIONAL.
**Decision.** The baseline is the untuned base model, zero-shot with the same prompt and decoding. No SFT baseline within the framework.
**Why.** The only SFT path seen in the repo requires a `p4d.24xlarge` (V14).
**Possible extension.** A few-shot baseline, or an SFT baseline using TRL outside the framework (future work).

### D-016: Sandboxed execution
**Status:** PROVISIONAL.
**Decision.** Execute generated SQL in a fresh in-memory SQLite database built from the example's context, read-only after setup, with a time limit, a result-size limit, and an authorizer that rejects non-SELECT statements and `ATTACH`/`PRAGMA`.
**Why.** Model output is untrusted; training will generate large volumes of it, including pathological queries.
**Open.** Timeout and row-limit values; whether to run in a subprocess for hard isolation; reward-call parallelism.

### D-017: Prompt content
**Status:** OPEN.
**Question.** Should the prompt include only `CREATE TABLE` statements, or also the `INSERT` rows?
**Considerations.** Including rows lets the model hard-code answers (`SELECT 42`) instead of writing a general query: a reward-hacking vector. Schema-only prompts match typical Text-to-SQL practice. A related safeguard: evaluate on databases populated differently from those used in training.
**Leaning.** Schema only, with data used solely for execution. Not yet decided.

### D-018: Python version and dependency split
**Status:** PROVISIONAL.
**Decision.** Python 3.12 via `uv`. The laptop installs only the base framework package. GPU dependencies (from `rl-train setup-local-gpu --recipe qwen3`) are installed only on the GPU machine.
**Why.** 3.12 is inside the supported range (V19) and widely supported by ML wheels; the split follows the framework's Quick Start (V8) and avoids installing CUDA stacks on a laptop.
**Open.** Phase 0 results (U8, U13); resolved versions to be recorded in the README pin table.

### D-019: Installable package
**Status:** PROVISIONAL.
**Decision.** Give our repository a `pyproject.toml` and install it editable on every machine.
**Why.** The task file is loaded in a training subprocess and imports our executor and reward code.
**Alternative.** Make the task file self-contained (less structure, duplicated code).

### D-020: Naming
**Status:** OPEN.
**Question.** The GitHub project is named `text2sql-grpo`. The Phase 0 instructions used a folder `sql-grpo` and a Python package `sqlgrpo`.
**Options.** Rename the folder and package to match the repo, or keep short internal names and document the difference. This does not affect function; it should be settled before any code is written, because imports and config paths depend on it.

### D-021: DeepSpeed on one GPU
**Status:** OPEN.
**Question.** The framework defaults to `ds_zero2_config.json` (V9). Is it needed, or even working, on one GPU? Where does the file live and how is the name resolved? (U4)
**Revisit.** Phase 0 inspection; Phase 4 smoke test.

### D-022: Fallback trigger
**Status:** PROVISIONAL.
**Decision.** If framework setup or configuration problems on the GPU machine consume more than about one working day without progress, switch to plain TRL `GRPOTrainer` with the same reward function and say so in the README.
**Why.** The one-day limit is a proposal intended to protect the schedule and budget.
**Note.** Everything in Phases 1–2 is framework-independent.

### D-023: LoRA settings
**Status:** OPEN.
**Known.** Framework defaults are `r: 32`, `alpha: 64`, `dropout: 0.05`, Qwen-style target modules (V11).
**Open.** Whether these suit a 1.7B model; whether a smaller rank is enough; whether LoRA is optional in the local GRPO path (not verified); how to load the adapter for evaluation, or whether to merge it.

### D-024: Scope exclusions
**Status:** PROVISIONAL.
**Decision.** Out of scope for the first version: LLM-judge rewards, the SageMaker and HyperPod backends, DPO/RLAIF, speculative decoding, load testing, and the framework's `evaluate`/`optimizer` operations.
**Why.** Keep the project small and the reward deterministic, in line with the owner's request to avoid unnecessary complexity and cost. The framework's `evaluate` command is not used because we need a custom executor-based evaluation anyway.

---

## Open questions summary

| Question | Related | Resolved by |
|---|---|---|
| What does `local_example.yaml` contain, and is its model small? | U1, D-007, D-010 | Phase 0 |
| What are the true GRPO defaults? | U5, D-011, D-012 | Read SageMaker doc, Phase 3 |
| Does the pinned stack run Qwen3-1.7B on one GPU? | U3, U11, D-007 | Phase 4 |
| What does TRL do with batch size vs K? | U7, D-011 | Phase 4 |
| Is DeepSpeed ZeRO-2 fine on one GPU? | U4, D-021 | Phase 0 / 4 |
| Schema only or schema plus data in the prompt? | D-017 | Phase 1 |
| Result comparison rules and reward values? | D-006 | Phase 2 |
| How are evaluation and the eval set made reproducible? | D-014 | Phase 1 |
| Which GPU provider and budget? | D-009 | Phase 4 |
| Adapter loading or merging for evaluation? | D-023 | Phase 7 |
| Final names for folder and package? | D-020 | Phase 0 |
| Licenses for publishing the adapter? | U12 | Phase 8 |
