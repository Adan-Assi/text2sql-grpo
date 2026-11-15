# Concepts

Background for readers new to RL fine-tuning. Each concept has four parts: **What it is**, **Why the project needs it**, **How it works**, and **Connection to the implementation**.

Tags: `[VERIFIED]` = read from a named source; `[PROPOSED]` = planned, not validated; `[OPEN]` = unresolved (see [DECISIONS.md](DECISIONS.md)). Project-specific choices live in DECISIONS.md and are not repeated here.

Contents: [Text-to-SQL](#1-text-to-sql) · [Fine-tuning](#2-llm-fine-tuning) · [LoRA](#3-lora) · [Reinforcement learning](#4-reinforcement-learning) · [Rollouts](#5-rollouts) · [Reward functions](#6-reward-functions) · [GRPO](#7-grpo) · [Advantage estimation](#8-advantage-estimation) · [Execution accuracy](#9-execution-accuracy) · [SQLite](#10-sqlite) · [vLLM](#11-vllm) · [TRL](#12-trl) · [DeepSpeed](#13-deepspeed) · [GPU memory](#14-gpu-memory)

---

## 1. Text-to-SQL

**What it is.** Translating a natural-language question into a SQL query, given the database schema.

**Why the project needs it.** It is the task being learned. It also has a built-in way to check answers: run the query.

**How it works.** The model sees a prompt such as:

```
Schema:   CREATE TABLE Beds (State VARCHAR(50), Beds INT);
Question: What is the total number of hospital beds in each state?
```

and generates `SELECT State, SUM(Beds) FROM Beds GROUP BY State;`. Typical failure modes: wrong column names, missing `GROUP BY`, invalid syntax, extra prose around the SQL, or a query that runs but answers a different question.

**Connection.** Each dataset row supplies question, schema, and gold SQL. The prompt contains the schema and question; the gold SQL is turned into a gold *result* in Phase 1. Whether the prompt shows only `CREATE TABLE` statements or also the data rows is `[OPEN]` (D-017), because showing data lets a model hard-code answers.

---

## 2. LLM fine-tuning

**What it is.** Continuing to train a pretrained model on a narrower task so it behaves better at that task.

**Why the project needs it.** A small general model writes mediocre SQL zero-shot. Fine-tuning adapts it to produce executable, correct queries in our prompt format.

**How it works.** There are two broad families:
- **Supervised fine-tuning (SFT):** show the model (prompt, target answer) pairs and train it to reproduce the target tokens.
- **Reinforcement learning (RL):** let the model generate its own answers, score them, and shift probability toward higher-scoring ones. No target string is required, only a way to score.

**Connection.** This project uses RL (GRPO). The local-backend doc says it "supports the same methods as SageMaker Training Jobs", and the config template comments list `grpo`, `sft`, and `dpo` `[VERIFIED: docs/launching-local-job.md]`. Which of these actually run on a single local GPU has not been tested `[OPEN]`. The only SFT path seen in the repo's smoke tests (`sft_verl`) needs a `p4d.24xlarge` instance `[VERIFIED: smoke_tests README]`, so we do not plan an in-framework SFT baseline `[PROPOSED]`. The baseline is the untuned model.

---

## 3. LoRA

**What it is.** Low-Rank Adaptation: freeze the original weights and train small extra matrices instead.

**Why the project needs it.** Full fine-tuning needs memory for gradients and optimizer states for every parameter. LoRA trains a tiny fraction, so a small GPU is enough, and the result is a small adapter file.

**How it works.** For a frozen weight matrix `W`, LoRA learns two thin matrices `A` and `B` and uses `W + (alpha / r) · B·A`. The rank `r` controls capacity (and size); `alpha` scales the update. Adapters are attached to chosen modules, usually the attention projections (`q_proj`, `k_proj`, `v_proj`, `o_proj`) and often the MLP projections.

**Connection.** The framework's `model.lora` block has `r` (default 32), `alpha` (default 64), `dropout` (default 0.05), and `target_modules` (Qwen-style defaults covering attention and MLP projections) `[VERIFIED: docs/launching-local-job.md]`. Whether those values suit a 1.7B model is `[OPEN]`. Evaluating the tuned model means loading the base model plus the adapter, or a merged copy `[OPEN: not yet decided]`.

---

## 4. Reinforcement learning

**What it is.** Learning by trial and feedback: an agent acts, receives a reward, and adjusts to earn more reward.

**Why the project needs it.** We want to optimize "the query returns the right rows" directly, and many different outputs satisfy that.

**How it works.** In the LLM setting: the *policy* is the model; an *action* is a generated token sequence (the whole completion is treated as one action); the *reward* is a number computed after the completion is finished. Training increases the probability of completions with above-average reward. A regularizer keeps the policy from drifting too far from the starting model.

**Connection.** Policy = Qwen3 + LoRA. Reward = execution-based function (below). The drift regularizer is the `beta` KL term in the GRPO config `[VERIFIED: appears in the docs' example config; chosen value for this project is OPEN]`.

---

## 5. Rollouts

**What it is.** The model's sampled attempts at a prompt during training.

**Why the project needs it.** RL learns from outcomes, so it first has to generate attempts to score.

**How it works.** For each prompt, the trainer samples K completions using randomness (temperature, top-p, top-k) so the attempts differ. Generation is usually the slowest part of an RL step.

**Connection.** `num_generations` is K; the docs' example uses 8 `[VERIFIED: example value, not a recommendation]`. Our K is `[OPEN]` (D-011). Sampling settings (`temperature`, `top_p`, `top_k`) are configurable under `training.grpo` `[VERIFIED]`. Evaluation does *not* use sampling; it uses greedy decoding `[PROPOSED]`.

---

## 6. Reward functions

**What it is.** A function that turns a completion into a number.

**Why the project needs it.** It is the only training signal. A reward that is easy to game teaches the model to game it.

**How it works.** The signal can be binary (right/wrong) or *shaped* with partial credit (for example, "runs without error" is better than "crashes"). Shaping helps early when few completions are fully correct, but can teach shortcuts. Common hacks to watch for: returning constants, or copying values seen in the prompt instead of querying.

**Connection.** The framework calls a function with the signature `reward_fn(completions, **dataset_columns) -> list[float]`, where each extra dataset column arrives as a list with one entry per completion; `completions` may be a list of strings or a list of chat-message lists `[VERIFIED: docs/tasks/creating-a-task.md]`. Our planned columns are `db_context` and `gold_result`. Reward tiers and values are `[PROPOSED]`/`[OPEN]` (D-006). Reward functions are plain Python and can be unit-tested without a GPU `[VERIFIED: same doc]`; that is the point of Phase 2.

---

## 7. GRPO

**What it is.** Group Relative Policy Optimization, an RL algorithm for LLMs. It estimates how good each completion is by comparing it to other completions *for the same prompt*, rather than using a separately trained value network (as in PPO).

**Why the project needs it.** It is simpler and lighter than PPO and works well with verifiable rewards. It is also the method the framework's local example is built around `[VERIFIED: examples/configs/README.md describes local_example.yaml as "GRPO on one local GPU"]`.

**How it works.** One training step:
1. Sample a batch of prompts.
2. Generate K completions per prompt (rollouts).
3. Score each completion with the reward function.
4. Convert scores to advantages within each group.
5. Update the weights: raise the probability of positive-advantage completions, lower it for negative ones. The update is clipped (`epsilon`, `epsilon_high`) for stability and penalized for straying from the reference model (`beta`).

If every completion in a group gets the same reward, all advantages are zero and that prompt teaches nothing. So training prompts should be neither always solved nor never solved by the base model `[PROPOSED heuristic]`.

**Connection.** In foresight-rl-core, GRPO is configured under `training.grpo` (for example `num_generations`, `max_completion_length`, `beta`, `loss_type`, `scale_rewards`) `[VERIFIED: example block in docs/launching-local-job.md; the full parameter reference in the SageMaker doc has not been read yet]`. The framework builds on TRL's `GRPOTrainer` `[VERIFIED: reward functions are documented as "compatible with TRL's GRPOTrainer"]`.

---

## 8. Advantage estimation

**What it is.** A number saying how much better or worse a completion was than expected.

**Why the project needs it.** Raw rewards are not enough. A reward of 0.6 is good if its siblings scored 0.1, and bad if they scored 1.0.

**How it works.** In GRPO the baseline is the group's mean reward. Two variants matter here:

- Original GRPO: `A_i = (r_i − mean) / std`
- Without std scaling: `A_i = r_i − mean` (the docs' example config sets `scale_rewards: false` together with `loss_type: dr_grpo`)

Worked example, K = 4, binary rewards `[1, 0, 0, 1]`: mean 0.5, std 0.5, so scaled advantages are `[+1, −1, −1, +1]`; unscaled are `[+0.5, −0.5, −0.5, +0.5]`. With rewards `[1, 1, 1, 1]` or `[0, 0, 0, 0]`, every advantage is 0 in both variants.

Dividing by std makes the update size independent of reward spread but can over-weight groups where nearly all answers are the same. The `dr_grpo` loss type is a variant designed to remove some such normalization effects; check TRL's documentation for its exact definition before relying on this description.

**Connection.** Which variant we use is `[OPEN]` (D-012). The relevant config keys are `training.grpo.scale_rewards` and `training.grpo.loss_type`.

---

## 9. Execution accuracy

**What it is.** The fraction of examples where the predicted query's *result* equals the gold query's result.

**Why the project needs it.** It is both the training signal (per example) and the headline evaluation metric (averaged over a held-out set). It is more forgiving of valid alternatives than exact string match.

**How it works.** Run the prediction and the gold query on the same database, then compare result sets. Choices to settle: compare as unordered multisets of rows unless the query has `ORDER BY`; column names or order; float tolerance; NULL handling; duplicates `[OPEN]` (D-006).

**Known weakness.** False positives: two different queries can return identical rows by coincidence, particularly when tables are tiny or the result is empty. Mitigations such as dropping examples with empty gold results are `[PROPOSED]`. The reverse error (a correct query judged wrong because of formatting differences) also occurs.

**Connection.** Implemented once in the executor and reused by the reward function (training) and the evaluation script, so the two cannot disagree `[PROPOSED]`.

---

## 10. SQLite

**What it is.** A small, serverless SQL database engine, available in Python's standard library as `sqlite3`.

**Why the project needs it.** It lets us build a throwaway database from each example's `CREATE TABLE`/`INSERT` text, in memory, thousands of times, with no server.

**How it works.** `sqlite3.connect(":memory:")` creates a private database; `executescript` runs the setup SQL; `execute(...).fetchall()` returns rows. Built-in hooks useful for safety: a progress handler (to abort long-running queries), an authorizer (to deny statements such as `ATTACH`), and read-only enforcement via `PRAGMA query_only`.

**Connection.** Model output is untrusted, so the planned executor is read-only, in-memory, time-limited, and restricted `[PROPOSED]` (D-016). SQLite is not PostgreSQL: some dataset queries may use syntax SQLite rejects, so every gold query must be executed and failures dropped in Phase 1 `[PROPOSED]`.

---

## 11. vLLM

**What it is.** A high-throughput inference engine for LLMs.

**Why the project needs it.** Generating K completions per prompt dominates training time; vLLM generates much faster than plain Hugging Face `generate`.

**How it works.** It batches many requests continuously and manages the attention cache efficiently. It reserves a fraction of GPU memory for itself.

**Connection.** The framework's local backend has three modes `[VERIFIED: docs/launching-local-job.md]`:

| `infra.vllm_mode` | Behavior |
|---|---|
| `server` | Separate vLLM process on dedicated GPUs; requires GPU count ≥ `vllm_gpu_count + training_gpu_count` |
| `colocate` | vLLM inside the trainer process; for memory-constrained setups |
| `none` | Native Hugging Face generation via `torchrun`; "small models, fast iteration" |

With one GPU, `server` is impossible, so the choice is `colocate` or `none`. `none` is the proposed starting point (D-010). The `qwen3` recipe installs vLLM (`trl[vllm]`) either way `[VERIFIED: recipe table]`. `infra.vllm.gpu_memory_utilization` defaults to 0.9 `[VERIFIED]`, which matters when sharing a GPU in `colocate` mode.

---

## 12. TRL

**What it is.** Hugging Face's library for training language models with RL and preference methods. It includes `GRPOTrainer`.

**Why the project needs it.** It does the actual GRPO work. foresight-rl-core is a configuration and orchestration layer on top of it.

**How it works.** You give `GRPOTrainer` a model, a dataset with a `prompt` column, and one or more reward functions. It generates completions, calls the reward functions, computes advantages, and updates the model.

**Connection.** Because our reward function follows TRL's signature, the same function can be passed to `GRPOTrainer` directly if the framework fails; this is the planned fallback (D-002, D-022). TRL's exact batch semantics (how per-device batch size, gradient accumulation, and `num_generations` combine) have not been verified `[OPEN]`; the working assumption is that the batch counts completions and must be divisible by `num_generations`.

---

## 13. DeepSpeed

**What it is.** A library for memory-efficient and distributed training.

**Why the project needs it.** Mostly it does not, on one GPU. It is included because the framework's defaults reference it.

**How it works.** ZeRO partitions optimizer states (stage 1), plus gradients (stage 2), plus parameters (stage 3) across GPUs so each holds only a slice. With one GPU there is nothing to partition, so the benefit is small.

**Connection.** The framework's `training.deepspeed` defaults to `ds_zero2_config.json` `[VERIFIED: docs table]`. Where that file lives and whether it works unchanged on one GPU are `[OPEN]` and to be checked in Phase 0/4.

---

## 14. GPU memory

**What it is.** The fixed pool of memory on the GPU that must hold everything needed for generation and training.

**Why the project needs it.** It decides which GPU to rent and whether a model size fits at all.

**How it works.** Rough budget, to be confirmed by measurement:
- **Weights:** parameters × bytes per parameter. A model of about 1.7 billion parameters in bf16 (2 bytes) is on the order of 3–4 GB.
- **LoRA parameters, gradients, optimizer states:** small, because only the adapter is trained.
- **Activations:** grow with batch size and sequence length; gradient checkpointing (default `true` in the docs) trades compute for lower activation memory `[VERIFIED]`.
- **Generation cache:** grows with number of completions × length; a main reason to cap `max_completion_length`.
- **vLLM reservation:** a fraction of GPU memory (default 0.9) if vLLM shares the GPU.

**Connection.** The 24 GB target is an estimate, not a measurement `[PROPOSED]`. The first GPU session (Phase 4) should record actual peak memory in [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md). The docs' example `max_completion_length` of 8192 is for long reasoning outputs and would waste memory for SQL; our value is `[OPEN]`.
