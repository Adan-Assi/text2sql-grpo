# Roadmap

Last updated: 2026-11-15

The current plan consists of nine phases (0–8), ordered by dependency. This file tracks **status**. Choices and their reasoning live in [DECISIONS.md](DECISIONS.md); background lives in [CONCEPTS.md](CONCEPTS.md); run records live in [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md).

## Status rules

| Status | Meaning |
|---|---|
| Not started | No work begun |
| In progress | Instructions issued or work begun, not all verification criteria met |
| Blocked | Waiting on a decision or external factor |
| Done (verified) | Every verification criterion met **and the evidence is recorded** |

## Overview

| Phase | Goal | Runs on | Status |
|---|---|---|---|
| 0 | Project skeleton, environment, clone framework, validate its example configs | Laptop | **In progress** (instructions issued; no results reported) |
| 1 | Dataset: download, filter, build SQLite databases, create train/eval JSONL | Laptop | Not started |
| 2 | Safe SQL executor and reward function, with unit tests | Laptop | Not started |
| 3 | foresight-rl-core task module, YAML config, `validate` | Laptop | Not started |
| 4 | First GPU session: setup, baseline eval, difficulty-based prompt selection, smoke test | Rented GPU | Not started |
| 5 | Short real run (~50 steps); read reward curves and samples | Rented GPU | Not started |
| 6 | Main run (300–600 steps) | Rented GPU | Not started |
| 7 | Final evaluation (base vs tuned), failure analysis, plots | Rented GPU, then laptop | Not started |
| 8 | README, results table, cleanup | Laptop | Not started |

Phase 4 step counts and the 300–600 step range come from the original proposal and are `[PROPOSED]`, not tuned.

## Gates

| Gate | After | Question | If "no" |
|---|---|---|---|
| G1 | Phase 0 | Does `rl-train validate` pass on the shipped example config without a GPU? | Diagnose before Phase 1; if unfixable, plan for TRL fallback (D-002) |
| G2 | Phase 4 | Does a 10-step mock-reward run complete on the rented GPU using our task and data? | Time-box debugging (D-022, about 1 day proposed); then switch to plain TRL with the same reward function |

---

## Phase 0: Workspace and framework check

**Status:** In progress. Setup instructions were given in conversation; the user has not yet reported output. Nothing below is verified.

**Objective.** A project folder with its own Python environment, the framework cloned alongside, and the framework's example configs validating on the laptop.

**Deliverables.**
- Project folder, git repository, `.gitignore`, directory skeleton (`src/sqlgrpo`, `tasks`, `configs`, `scripts`, `tests`, `data`, `third_party`; `docs` added with this documentation).
- Virtual environment (Python 3.12 proposed, D-018).
- `third_party/foresight-rl-core` cloned; commit hash recorded.
- Framework installed in editable mode.

**Verification criteria.**
- `rl-train --help` runs inside the environment.
- `rl-train validate` exits cleanly on `examples/configs/local_example.yaml`, run from the clone's root if relative paths require it.
- Commit hash recorded in the README pin table.
- Output of the evidence-gathering commands saved (see tasks).

**Remaining tasks.**
- [ ] Run the Phase 0 commands; report OS, GPU presence (`nvidia-smi`), and all errors.
- [ ] Record `git rev-parse HEAD` of the clone.
- [ ] Check whether the base install pulled in torch or other heavy packages (`uv pip list`).
- [ ] Read and share `examples/configs/local_example.yaml`.
- [ ] Locate the shipped task that uses `outcome_category` and read its loader and reward code.
- [ ] Run `rl-train setup-local-gpu --list` and read `LOCAL_GPU_RECIPES` in `foresightrlcore/config/recipes.py`.
- [ ] Locate `ds_zero2_config.json`.
- [ ] Resolve the naming question (D-020).
- [ ] Commit the skeleton and these docs.

---

## Phase 1: Dataset

**Status:** Not started.

**Objective.** Turn `gretelai/synthetic_text_to_sql` into train and eval JSONL files whose rows contain everything the reward function needs, with gold results precomputed and verified.

**Deliverables** (file names `[PROPOSED]`).
- A data-prep module in `src/sqlgrpo/` and a script in `scripts/`.
- `data/train.jsonl`, `data/eval.jsonl` (git-ignored), with `prompt` (chat messages) plus `db_context` and `gold_result` columns, following the framework's documented format `[VERIFIED: extra columns become reward kwargs]`.
- A short data report: counts at each filtering stage.
- `pyproject.toml` so `sqlgrpo` is installable (D-019).

**Verification criteria** `[PROPOSED]`.
- Dataset fields match the dataset card; split sizes recorded.
- Only SELECT-type examples kept; rule documented.
- Every kept gold query executes in SQLite; the fraction dropped is reported.
- Gold results non-empty, or the rule for empty ones is documented.
- No example appears in both train and eval; eval set fixed and seeded.
- A sample of rows inspected by eye.

**Remaining tasks.**
- [ ] Decide prompt content: schema only, or schema plus data (D-017).
- [ ] Decide eval set size and construction (D-014).
- [ ] Decide how the eval set is made reproducible given `data/` is git-ignored.
- [ ] Decide result serialization for `gold_result`.

---

## Phase 2: Executor and reward function

**Status:** Not started.

**Objective.** A deterministic, sandboxed SQL executor and a reward function built on it, tested without a GPU.

**Deliverables** (`[PROPOSED]`).
- `src/sqlgrpo/executor.py`: build database from context, run a query with limits, return rows or an error category.
- `src/sqlgrpo/reward.py`: SQL extraction from completions (strings and chat-message lists), tiered scoring.
- Unit tests in `tests/`.

**Verification criteria** `[PROPOSED]`.
- Tests cover: correct query, wrong-result query, syntax error, unknown table/column, empty output, code-fenced output, extra prose, infinite or very slow query (timeout), forbidden statements (`ATTACH`, writes), different-but-equivalent query, order sensitivity.
- Reward is deterministic across repeated calls.
- Gold SQL scores the maximum on a sample of dataset rows.
- A batch of 100+ completions scores in a reasonable time on a laptop (threshold to be set).

**Remaining tasks.**
- [ ] Settle result comparison rules (D-006).
- [ ] Choose reward tier values (D-006).
- [ ] Choose timeout and row-limit values.

---

## Phase 3: Framework task module and config

**Status:** Not started.

**Objective.** Wrap the reward and data in the framework's task protocol and write a config that passes `rl-train validate`.

**Deliverables** (`[PROPOSED]`).
- `tasks/text_to_sql.py` exporting `get_reward_function`, `get_callbacks`, `get_dataset_loader` `[VERIFIED: protocol from docs/tasks/creating-a-task.md]`, including a `mock` reward mode as the docs recommend.
- A loader accepting both a file path and a directory (the docs' example loader globs a directory, while the shipped local config points at a single file).
- YAML config(s) in `configs/` for mock and real runs, using `task.type` as a `.py` file path `[VERIFIED: supported resolution order]`.

**Verification criteria** `[PROPOSED]`.
- `rl-train validate` passes on the configs.
- Task module imports on a CPU-only machine.
- Loader returns a dataset whose `prompt` field is in the form the trainer expects and whose extra columns reach the reward function (checked with a stub call).
- Reward function called via the task module matches Phase 2 results.

**Remaining tasks.**
- [ ] Read the full GRPO parameter reference in `docs/launching-sagemaker-training-job.md`.
- [ ] Choose all hyperparameters (D-007, D-008, D-010, D-011, D-012, D-021, D-023).
- [ ] Confirm how a file-path task and relative paths resolve in the training subprocess.

---

## Phase 4: First GPU session

**Status:** Not started. Blocked on Phases 0–3 and on D-009 (GPU provider).

**Objective.** Prove the pipeline end to end on rented hardware, measure the baseline, and choose training prompts.

**Deliverables** (`[PROPOSED]`).
- Reproducible GPU setup script (framework, recipe dependencies, our package).
- Baseline evaluation of the untuned model on the eval set, with the same executor.
- Per-prompt base-model pass rates on the training split; filtered training set.
- A 10-step mock-reward run (`training.max_steps: 10`, mock reward mode) `[VERIFIED: pattern documented for the advice task]`.
- Recorded peak GPU memory and time per step.
- Optional, if `local_example.yaml` uses a small model: run it unmodified first, to separate framework problems from ours `[PROPOSED]`.

**Verification criteria** `[PROPOSED]`.
- Mock run completes 10 steps and writes outputs.
- Baseline accuracy computed and logged in the experiment log with config and revisions.
- Pass-rate distribution inspected; a usable subset exists (the 20–70% band is a heuristic, D-013).
- Instance terminated after the session; cost noted.

**Remaining tasks.**
- [ ] Choose provider and instance (D-009).
- [ ] Verify `vllm_mode` choice on one GPU (D-010).
- [ ] Verify TRL batch semantics against `num_generations` (D-011).
- [ ] Check whether DeepSpeed ZeRO-2 works unchanged on one GPU (D-021).

---

## Phase 5: Short real run

**Status:** Not started.

**Objective.** A ~50-step run with the real reward to check that learning signals look sane before spending on the main run.

**Deliverables.** Logged reward curve and completion samples; notes on any hacking or instability; a go/no-go for Phase 6.

**Verification criteria** `[PROPOSED]`.
- Reward values span the tiers (not all identical).
- Sample completions read by a human.
- No divergence, empty outputs, or obvious gaming.
- Throughput and memory acceptable for the planned run length.

**Remaining tasks.**
- [ ] Decide reward normalization and loss type (D-012).
- [ ] Decide learning rate and batch settings.

---

## Phase 6: Main run

**Status:** Not started.

**Objective.** The main training run (300–600 steps proposed).

**Deliverables.** Checkpoints/adapter; training logs; experiment-log entry with full config.

**Verification criteria** `[PROPOSED]`.
- Run completes; adapter saved and loadable.
- Reward trend inspected, with any plateau or collapse noted.
- Checkpoints copied off the rented machine before termination.

**Remaining tasks.**
- [ ] Decide checkpoint frequency and which checkpoint to evaluate.
- [ ] Decide whether to run extra seeds or ablations (scope-dependent).

---

## Phase 7: Final evaluation and analysis

**Status:** Not started.

**Objective.** A fair base-vs-tuned comparison with failure analysis.

**Deliverables.** Evaluation script and outputs; results table; plots; categorized failure cases; hacking check.

**Verification criteria** `[PROPOSED]`.
- Same prompts, executor, and decoding for both models.
- Eval examples confirmed disjoint from training data.
- Uncertainty reported (a 300-example eval has roughly ±3 percentage points standard error near 50% accuracy).
- Optional out-of-distribution check run and reported, or explicitly skipped.

**Remaining tasks.**
- [ ] Decide on the out-of-distribution benchmark (D-014).
- [ ] Decide how the adapter is loaded for evaluation (adapter vs merged).

---

## Phase 8: Documentation and cleanup

**Status:** Not started.

**Objective.** A repository others can understand and reproduce.

**Deliverables.** README with real results and reproduction steps; filled pin table; experiment log complete; license chosen; adapter published only after license check.

**Verification criteria** `[PROPOSED]`.
- Every `TODO` in the README is resolved or removed.
- Reproduction steps followed from scratch on a clean machine, or the gap stated.
- Every reported number traces to an experiment-log entry.

**Remaining tasks.**
- [ ] Choose a license; check upstream licenses.

---

## Amendment log

| Date | Change | Status |
|---|---|---|
| 2026-11-15 | Phase 3 to include a mock reward mode and a loader that accepts file or directory | `[PROPOSED]`, not yet agreed |
| 2026-11-15 | Phase 1/2 to add `pyproject.toml` and install our package, so the task file can import it in the training subprocess | `[PROPOSED]`, not yet agreed |
| 2026-11-15 | Phase 4 to optionally run the shipped `local_example.yaml` first | `[PROPOSED]`, not yet agreed |
