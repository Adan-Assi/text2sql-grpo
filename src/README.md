## Source Code Structure

The project uses an `src/` layout to separate the installable Python package from project-level files such as scripts, tests, and documentation.

The `text2sql_grpo/` directory inside `src/` is the actual Python package. Grouping the related modules under one package gives them a shared namespace, makes imports consistent, and allows the project to be installed and reused as a package rather than treating each file as a standalone module.

| File | Purpose |
|---|---|
| [`__init__.py`](text2sql_grpo/__init__.py) | Marks the directory as a Python package and provides a place for package-level definitions or exports. |
| [`executor.py`](text2sql_grpo/executor.py) | Handles SQLite database construction and SQL query execution, including execution safety and result handling. |
| [`data_prep.py`](text2sql_grpo/data_prep.py) | Prepares the dataset by applying filtering and validation steps, then generates the processed dataset and preparation reports. |
| [`prompts.py`](text2sql_grpo/prompts.py) | Defines the prompt format used to present database schemas and natural-language questions to the model. |

This structure keeps responsibilities separated: dataset preparation, SQL execution, and prompt construction can be developed and tested independently while remaining part of the same package.