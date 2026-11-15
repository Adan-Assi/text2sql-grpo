# Experiment log

Last updated: 2026-11-15

**No experiments have been run.** This file is a template and index. Every number reported in the README must trace to an entry here. Phase context is in [ROADMAP.md](ROADMAP.md); the choices being tested are in [DECISIONS.md](DECISIONS.md).

## Rules

1. **One entry per run**, including failed, aborted, and smoke-test runs. A failed run with a recorded cause is useful.
2. **Write the entry before the run** (Setup and Hypothesis sections), and fill in Results and Observations afterward. Do not edit the Hypothesis after seeing results.
3. **Record only what was measured.** Mark anything inferred as such.
4. **Keep entries self-contained.** Link the config file, but also paste the key settings, because configs change.
5. **Never reuse an ID.** If an entry is wrong, add a correction note rather than deleting it.

## ID convention

`EXP-NNN`, numbered in order of creation. Add a short type tag in the title: `[smoke]`, `[baseline]`, `[train]`, `[eval]`, `[ablation]`, `[debug]`.

## Index

| ID | Date | Type | Phase | Model | Summary | Outcome |
|---|---|---|---|---|---|---|
| | | | | | | |

*Outcome values:* `completed`, `failed`, `aborted`, `superseded`.

---

## Entry template

Copy everything below this line for each new entry.

### EXP-NNN: [type] Short title

**Date:** YYYY-MM-DD  **Phase:** N  **Status:** planned / running / completed / failed / aborted
**Operator:** 
**Related decisions:** D-0xx, …

#### 1. Purpose and hypothesis
What question does this run answer? What do you expect, and why? What result would change a decision?

#### 2. Setup

| Item | Value |
|---|---|
| Project repo commit | |
| foresight-rl-core commit | |
| Config file path + hash | |
| Task module path + hash | |
| Python version | |
| Key package versions (torch, trl, transformers, vllm, peft, deepspeed) | |
| Base model + revision | |
| Adapter / checkpoint used (if any) | |
| Dataset name + revision | |
| Data files used (train / eval) + row counts + hash | |
| Random seed(s) | |

#### 3. Configuration (key settings)

| Setting | Value |
|---|---|
| `infra.vllm_mode` | |
| `model.enable_thinking` | |
| `model.lora` (r / alpha / dropout / target modules) | |
| `training.grpo.num_generations` (K) | |
| `training.grpo.max_completion_length` | |
| `training.grpo.beta` | |
| `training.grpo.loss_type` | |
| `training.grpo.scale_rewards` | |
| `training.grpo` sampling (temperature / top_p / top_k) | |
| `training.learning_rate` | |
| `training.per_device_batch_size` × `gradient_accumulation_steps` | |
| `training.max_steps` / epochs | |
| `training.bf16`, `deepspeed` config | |
| Reward mode and tier values | |
| Executor limits (timeout, row cap) | |
| Evaluation decoding (greedy? max new tokens) | |

*Full config attached or linked:* 

#### 4. Hardware and cost

| Item | Value |
|---|---|
| Provider / instance | |
| GPU model, count, memory | |
| Driver / CUDA version | |
| Wall-clock time (setup / run / total) | |
| Billed time and cost | |
| Peak GPU memory observed | |
| Time per training step | |
| Instance terminated? (time) | |

#### 5. Metrics

*Training runs:*

| Metric | Start | Mid | End | Notes |
|---|---|---|---|---|
| Mean reward | | | | |
| Fraction of completions with reward at each tier | | | | |
| Fraction of groups with zero reward variance | | | | |
| Mean completion length | | | | |
| KL / loss (as logged) | | | | |

*Evaluation runs:*

| Metric | Value | Eval set / n | Notes |
|---|---|---|---|
| Execution accuracy | | | |
| Valid-SQL rate (executes without error) | | | |
| Timeout rate | | | |
| Empty-output / no-SQL rate | | | |
| Standard error or confidence interval | | | |
| Accuracy by `sql_complexity` (if reported) | | | |

#### 6. Results
Short factual summary of what happened. Include links to logs, TensorBoard exports, plots, and prediction files.

#### 7. Observations
- What looked as expected?
- What looked wrong or surprising?
- Sample completions reviewed (IDs, with good and bad examples).
- Any sign of reward hacking, collapse, or instability?

#### 8. Problems encountered
Errors, workarounds, and their fixes. Quote exact error messages.

#### 9. Conclusions and next steps
What this run does and does not show. Which decision does it affect? What is the next experiment?

#### 10. Corrections (append-only)
Date + note, if anything above is later found to be wrong.

---

## Suggested entries by phase

Only a guide to what typically gets logged; create entries when runs actually happen.

| Phase | Typical entries |
|---|---|
| 0 | Framework `validate` check (`[debug]` or `[smoke]`) |
| 1 | Data build report: counts per filtering stage (`[debug]`) |
| 4 | Optional shipped-example run; mock-reward smoke run; baseline evaluation; per-prompt pass-rate sampling |
| 5 | Short real run |
| 6 | Main run; any ablations |
| 7 | Final evaluation of base and tuned models; hacking check; optional out-of-distribution evaluation |
