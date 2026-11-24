
# Text-to-SQL GRPO

An experimental project exploring reinforcement learning for Text-to-SQL: fine-tuning a language model to generate SQLite queries from natural-language questions and database schemas using execution-based rewards.

## Project Overview

The goal is to train a small open language model to translate natural-language questions into SQL queries using **Group Relative Policy Optimization (GRPO)**.

Instead of rewarding the model for reproducing the exact reference SQL, the intended reward is based on whether the generated query executes successfully and returns the correct result.

The project uses SQLite as the execution environment and SQaLe 2 as its primary dataset.

## How It Works

The planned training pipeline consists of:

1. **Dataset preparation:** Load questions, database schemas, and reference queries.
2. **Database execution:** Reconstruct the corresponding SQLite databases and execute generated SQL queries.
3. **Reward calculation:** Compare query execution results with the reference results.
4. **GRPO training:** Use execution-based rewards to optimize the model.
5. **Evaluation:** Compare the base model and fine-tuned model using execution accuracy.

## Current Progress

Work is currently focused on the execution infrastructure and dataset preparation.

### Implemented so far

- **SQLite executor:** Utilities for creating in-memory databases, retrieving schema information, and executing SQL queries.
- **Read-only protection:** Added SQLite connection restrictions using `PRAGMA query_only` and a SQLite authorizer to restrict SQL operations.
- **Dataset exploration:** Selected SQaLe 2 and inspected its structure, query formats, and database reconstruction utilities.
- **Dataset auditing:** Started examining query types and checking the reliability of reconstructed databases and stored execution results.
- **Project environment:** Set up a Python 3.12 environment and dependency management with `uv`.
- **Testing setup:** Added `pytest` as a development dependency.

### Not implemented yet

- Final dataset preparation and train/evaluation splits.
- Reward function.
- Model selection and configuration.
- GRPO training integration.
- Training and evaluation runs.

## Technology Stack

- **Languages:** Python, SQL
- **Database:** SQLite
- **Dataset:** SQaLe 2
- **Libraries:** Hugging Face Datasets, SQaLe
- **Testing:** pytest
- **Environment and dependency management:** uv
- **Version control:** Git, GitHub

## Project Structure

```text
text2sql_grpo/
├── docs/
│   ├── CONCEPTS.md
│   ├── DATASET_SUITABILITY_ASSESSMENT.md
│   ├── DECISIONS.md
│   ├── EXPERIMENT_LOG.md
│   ├── PROJECT_CONCEPTS.md
│   └── ROADMAP.md
├── reports/
│   └── smoke/
│       └── README.md
├── scripts/
│   ├── audit_experiment_4.py
│   ├── audit_experiment_5.py
│   ├── audit_sqale2_fidelity.py
│   ├── audit_sqale2_query_types.py
│   └── README.md
├── src/
│   ├── README.md
│   └── text2sql_grpo/
│       ├── __init__.py
│       ├── data_prep.py
│       ├── executor.py
│       └── prompts.py
├── tests/
│   ├── test_executor_manual.py
│   └── test_executor_safety.py
├── third_party/
│   └── foresight-rl-core/
├── data/                 # Git-ignored dataset files
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
```

## Setup

Requires Python 3.12 or later and [uv](https://docs.astral.sh/uv/).

Clone the repository and install the project dependencies:

```bash
uv sync
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

## Dataset

The project uses [SQaLe 2](https://huggingface.co/datasets/trl-lab/SQaLe-2-text-to-SQL-Queries), a Text-to-SQL dataset containing natural-language questions, SQL queries, and associated database information.

Dataset preparation and validation are ongoing.

## Status

This project is under active development. The execution infrastructure and initial dataset investigation are underway. Model training and evaluation have not yet started.
