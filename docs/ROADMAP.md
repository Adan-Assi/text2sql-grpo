# Roadmap

Last updated: 2026-11-25

This roadmap tracks the project's progress across nine phases (0–8), ordered by dependency.

- **[DECISIONS.md](DECISIONS.md):** Decisions and their reasoning.
- **[CONCEPTS.md](CONCEPTS.md):** Background concepts and explanations.
- **[EXPERIMENT_LOG.md](EXPERIMENT_LOG.md):** Experiment configurations, results, and observations.

## Status rules

| Status | Meaning |
|---|---|
| Not started | No work begun |
| In progress | Work has begun, but verification criteria are not all met |
| Blocked | Waiting on a decision or external factor |
| Done (verified) | All verification criteria met and evidence recorded |

## Overview

| Phase | Goal | Environment | Status |
|---|---|---|---|
| 0 | Project setup and framework validation | Laptop | In progress |
| 1 | Dataset preparation and validation | Laptop | In progress |
| 2 | SQL execution, safety, and reward implementation | Laptop | In progress |
| 3 | Foresight task module and training configuration | Laptop | Not started |
| 4 | GPU setup, baseline evaluation, and pipeline smoke test | GPU | Not started |
| 5 | Short training run | GPU | Not started |
| 6 | Main training run | GPU | Not started |
| 7 | Final evaluation and analysis | GPU / Laptop | Not started |
| 8 | Documentation and cleanup | Laptop | In progress |

## Phase 0: Project setup and framework validation

**Status:** In progress

**Objective:** Establish the development environment and verify that the Foresight RL Core framework can run on the laptop.

**Completed:**
- Created the project repository and initial directory structure.
- Initialized the Python project using `uv`.
- Set up the virtual environment and installed initial dependencies.
- Cloned Foresight RL Core into `third_party/`.
- Installed the framework locally for development.

**Remaining:**
- [ ] Verify the framework CLI works.
- [ ] Run `rl-train validate` on a shipped example configuration.
- [ ] Record the framework commit hash.
- [ ] Review the framework's example task and configuration.
- [ ] Record the setup and validation results.

**Verification criteria:**
- Framework CLI runs inside the project environment.
- A shipped example configuration passes validation.
- Framework version and setup details are recorded.

## Phase 1: Dataset preparation

**Status:** In progress

**Objective:** Prepare SQaLe 2 examples for Text-to-SQL training and evaluation.

**Completed:**
- Selected SQaLe 2 as the primary dataset.
- Loaded the dataset using the Hugging Face Datasets library.
- Inspected the SQaLe package and its database reconstruction utilities.
- Audited a sample of 500 queries: 455 SELECT queries and 45 WITH queries.
- Started investigating database reconstruction fidelity.

**Remaining:**
- [ ] Complete the dataset and database reconstruction audits.
- [ ] Define filtering and train/evaluation split rules.
- [ ] Implement the data preparation pipeline.
- [ ] Build the SQLite databases needed by the examples.
- [ ] Execute and validate gold queries.
- [ ] Generate the training and evaluation JSONL files.
- [ ] Inspect prepared examples and record dataset statistics.

**Verification criteria:**
- Dataset filtering and split rules are documented.
- Training and evaluation examples do not overlap.
- Gold queries execute successfully against their reconstructed databases, or failures are accounted for.
- Prepared examples contain the information required by the training and reward pipeline.
- Dataset statistics and representative examples are recorded.

## Phase 2: SQL executor and reward

**Status:** In progress

**Objective:** Implement a reliable SQL execution component and an execution-based reward function.

**Completed:**
- Implemented SQLite database creation and query execution utilities.
- Added read-only protections using SQLite's `query_only` setting and an authorizer allowlist.
- Added initial executor tests and started developing a safety-focused test suite.

**Remaining:**
- [ ] Complete and run tests against the actual executor implementation.
- [ ] Verify that permitted queries work and prohibited operations are rejected.
- [ ] Address execution limits and other relevant safety protections.
- [ ] Implement SQL extraction from model completions.
- [ ] Implement result comparison and the reward function.
- [ ] Test reward behavior on representative dataset examples.

**Verification criteria:**
- Valid SELECT queries execute correctly.
- Invalid SQL and prohibited operations are handled safely.
- Query execution has appropriate resource limits.
- Result comparison and reward calculation are deterministic.
- Gold queries receive the expected maximum reward.
- Tests run successfully without requiring a GPU.

## Phase 3: Framework task module and configuration

**Status:** Not started

**Objective:** Integrate the dataset and reward function with Foresight RL Core.

**Planned work:**
- Implement the Text-to-SQL task module.
- Connect the dataset loader and reward function to the framework.
- Create training configurations.
- Support mock-reward execution for pipeline testing.

**Verification criteria:**
- Task module imports successfully on a CPU-only machine.
- Dataset loader provides data in the expected format.
- Reward function receives the required example fields.
- Training configurations pass framework validation.

## Phase 4: GPU setup and pipeline smoke test

**Status:** Not started

**Objective:** Set up the training environment, evaluate the base model, and verify the complete pipeline before a real training run.

**Planned work:**
- Set up the selected GPU environment and dependencies.
- Run baseline evaluation on the held-out evaluation set.
- Inspect base-model performance on training examples.
- Run a short mock-reward training session.
- Record runtime, memory usage, and setup details.

**Verification criteria:**
- GPU environment is operational.
- Baseline evaluation completes and results are recorded.
- Mock-reward training completes successfully.
- Training outputs and environment details are saved.

## Phase 5: Short training run

**Status:** Not started

**Objective:** Run a short training experiment with the actual reward function before committing resources to the main run.

**Planned work:**
- Run approximately 50 training steps.
- Inspect reward trends and generated SQL samples.
- Check for unstable training behavior or reward exploitation.
- Decide whether the setup is ready for the main run.

**Verification criteria:**
- Training completes successfully.
- Reward values and generated samples are inspected.
- No critical training or execution issues remain unresolved.

## Phase 6: Main training run

**Status:** Not started

**Objective:** Run the main GRPO fine-tuning experiment.

**Planned work:**
- Run the planned training configuration.
- Monitor training metrics and generated samples.
- Save checkpoints and training logs.
- Preserve the final model adapter and experiment configuration.

**Verification criteria:**
- Training completes or any interruption is documented.
- Model artifacts and logs are saved.
- Training behavior and final checkpoint are reviewed.

## Phase 7: Final evaluation and analysis

**Status:** Not started

**Objective:** Compare the fine-tuned model against the base model and analyze the results.

**Planned work:**
- Evaluate both models on the same held-out examples.
- Compare execution accuracy and SQL validity.
- Analyze common failure cases.
- Inspect whether the reward function encouraged unintended behavior.
- Generate result tables and plots.

**Verification criteria:**
- Both models are evaluated under consistent conditions.
- Evaluation results are recorded and reproducible.
- Performance differences and limitations are analyzed.
- Relevant failure cases are documented.

## Phase 8: Documentation and cleanup

**Status:** In progress

**Objective:** Prepare the repository and project documentation to clearly explain the implementation, experiments, and findings.

**Completed:**
- Updated the README to reflect the project's current direction and progress.
- Reviewed and corrected the documented project structure.

**Remaining:**
- [ ] Document the final implementation and setup instructions.
- [ ] Add experiment results and analysis to the README.
- [ ] Complete the experiment log.
- [ ] Remove outdated or unused files and documentation.
- [ ] Review dependency and licensing requirements.

**Verification criteria:**
- README accurately reflects the final project.
- Setup and reproduction instructions are documented.
- Reported results can be traced to experiment records.
- Repository structure and documentation are consistent.