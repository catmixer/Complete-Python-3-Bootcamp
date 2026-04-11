# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Repository Overview

This is the **Complete Python 3 Bootcamp** course repository — the official course files for Jose Portilla's Udemy Python 3 Bootcamp. It is an **educational content repository**, not an application codebase. There is no build system, no package to install, no CI, and no top-level entry point. The content is delivered almost entirely as Jupyter notebooks that students run interactively.

- **Primary content**: 185 Jupyter notebooks (`.ipynb`)
- **Supporting scripts**: ~17 standalone `.py` files used in specific lessons
- **Docs at root**: `README.md`, `FAQ.ipynb`, `Jupyter (iPython) Notebooks Guide.ipynb`

## Directory Layout

The repository is organized into 18 numbered top-level sections that follow the course curriculum in order. Each folder is self-contained and does not import from sibling sections.

```
00-Python Object and Data Structure Basics/  # numbers, strings, lists, dicts, tuples, sets, files
01-Python Comparison Operators/
02-Python Statements/                         # if/elif/else, loops, comprehensions, Guessing Game challenge
03-Methods and Functions/                     # functions, lambda, *args/**kwargs
04-Milestone Project - 1/                     # Tic-Tac-Toe style project (assignment + walkthrough + solutions)
05-Object Oriented Programming/
06-Modules and Packages/                      # Contains real .py files and a package example
    00-Modules_and_Packages/
        mymodule.py, myprogram.py
        MyMainPackage/
            __init__.py, some_main_script.py
            SubPackage/
                __init__.py, mysubscript.py
    01-Name_and_Main/                         # one.py, two.py + Explanation.txt for if __name__ == "__main__"
07-Errors and Exception Handling/             # cap.py + test_cap.py (unittest demo), simple1.py, simple2.py
08-Milestone Project - 2/                     # Card / Blackjack style project
09-Built-in Functions/                        # map, reduce, filter, zip, enumerate, all/any, complex
10-Python Decorators/
11-Python Generators/
12-Final Capstone Python Project/
    Projects-Solutions/Solution Links.md
13-Advanced Python Modules/                   # collections, datetime, pdb, timeit, re, StringIO
14-Advanced Python Objects and Data Structures/
15-Advanced OOP/
16-Bonus Material - Introduction to GUIs/     # ipywidgets (Jupyter widgets)
17-Parallel Processing/                       # test.py, test2.py + multithreading/multiprocessing notebook
```

### Naming conventions inside sections

- Files are prefixed with a two-digit ordering number: `01-...ipynb`, `02-...ipynb`.
- **Homework / assessment notebooks** come in pairs: the exercise notebook and a matching `... - Solution.ipynb` (or `...-Solutions.ipynb`). Example: `08-Functions and Methods Homework.ipynb` + `09-Functions and Methods Homework - Solutions.ipynb`.
- **Milestone / Capstone projects** use a consistent four-notebook pattern:
  1. `01-... Assignment.ipynb`
  2. `02-... Walkthrough Steps Workbook.ipynb`
  3. `03-... Complete Walkthrough Solution.ipynb`
  4. `04-... Solution Code.ipynb` (or an Advanced Solution)
- Directory/file names contain spaces — always quote paths in shell commands.

## Working with the Code

### Runtime / dependencies

- Target language: **Python 3** (no explicit minimum pinned in the repo).
- There is **no `requirements.txt`, `setup.py`, `pyproject.toml`, or lockfile**. Dependencies are implied by each notebook.
- Notebooks rely on **Jupyter** (`jupyter notebook` or `jupyter lab`) and, in isolated sections, on packages such as `ipywidgets` (section 16), `numpy` (advanced numbers), or the standard library (most sections). Install these ad-hoc only when a specific notebook requires them.
- The supporting `.py` files use only the Python standard library (e.g. `unittest`, `threading`, `multiprocessing`).

### Running notebooks

```bash
jupyter notebook                 # or: jupyter lab
```

Open the desired `.ipynb` from the browser. Solutions are meant to be read after attempting the exercise notebook of the same name.

### Running the standalone Python scripts

These are the only `.py` files that are meant to be executed directly. Always `cd` into the containing directory first, because several of them use relative imports:

```bash
cd "06-Modules and Packages/00-Modules_and_Packages"
python myprogram.py                    # imports MyMainPackage

cd "06-Modules and Packages/01-Name_and_Main"
python one.py                          # demonstrates __name__ == "__main__"
python two.py

cd "07-Errors and Exception Handling"
python -m unittest test_cap.py         # unit-test example (tests cap.py)
python simple1.py                      # deliberately raises; used to show tracebacks

cd "17-Parallel Processing"
python test.py
python test2.py
```

`cap.py` / `test_cap.py` in section 07 is the canonical pytest-free `unittest` demo in this repo — prefer preserving its exact shape when editing, since the lesson narrative in `04-Unit Testing.ipynb` references the file verbatim.

## Editing Guidance for AI Assistants

Because this is course material, changes carry different risk than a typical app repo. Follow these rules:

1. **Preserve pedagogical intent.** Notebooks are teaching artifacts. Do not refactor for elegance, shorten explanations, rename variables for style, or "modernize" idioms (e.g. replacing `str.format` with f-strings, rewriting loops as comprehensions) unless the user explicitly asks. Students are following along with the printed/video lessons.
2. **Don't "fix" intentional errors.** Files like `07-Errors and Exception Handling/simple1.py` and several cells in the exception-handling notebooks raise on purpose. Verify before changing any code that looks broken.
3. **Keep exercise and solution notebooks in sync.** If you change a homework prompt, update the matching `... - Solution.ipynb`, and vice versa. Milestone projects need all four notebooks kept consistent.
4. **Notebook edits must produce valid JSON.** `.ipynb` files are JSON. Prefer editing a single cell's `source` array rather than rewriting the whole file. When you do rewrite, make sure `nbformat`, `nbformat_minor`, `cell_type`, `metadata`, `outputs`, and `execution_count` fields are preserved for existing cells. If outputs are already stored in a cell, leave them alone unless the task is specifically to clear or regenerate them.
5. **Don't auto-execute notebooks** as part of a task. Re-running cells can mutate outputs and inflate diffs. Only re-run when the user asks for it.
6. **Don't create new top-level files** (new sections, README variants, requirements files, CI configs) unless requested. This repo has no packaging and adding any would be out of character.
7. **Avoid committing `__pycache__/`**. Several folders already have them tracked historically; do not add new entries.
8. **Paths contain spaces.** Always quote: `"04-Milestone Project - 1/01-Milestone Project 1 - Assignment.ipynb"`. This affects `cd`, `python`, and any shell tool.

## Git Workflow for This Session

This session is constrained to a specific development branch (see the operator instructions). Key points:

- **Active branch**: `claude/add-claude-documentation-3WGt1`
- **Upstream remote**: `origin` (fork: `catmixer/complete-python-3-bootcamp`)
- All commits from this assistant should land on the designated branch. Do not push to `master` or to any other branch.
- Push with `git push -u origin claude/add-claude-documentation-3WGt1`, retrying on transient network errors only.
- Do **not** open a pull request unless the user explicitly asks.
- GitHub interactions use the `mcp__github__*` MCP tools — the `gh` CLI is not available. MCP tools are scoped to `catmixer/complete-python-3-bootcamp`; attempts against any other repo will be denied.

## Quick Reference: What Lives Where

| Need | Look in |
| --- | --- |
| Python language basics (types, control flow, functions) | 00 – 03 |
| OOP | 05, 15 |
| First full mini-project | 04 (Milestone 1) |
| Modules / packages / `__name__` | 06 |
| Exceptions + unit testing demo | 07 (`cap.py`, `test_cap.py`) |
| Card game / second mini-project | 08 (Milestone 2) |
| Functional-style built-ins | 09 |
| Decorators / generators | 10, 11 |
| Capstone project ideas + solution links | 12 |
| Standard library deep dives (`re`, `datetime`, `pdb`, `timeit`) | 13 |
| Jupyter widgets tutorial | 16 |
| `threading` / `multiprocessing` examples | 17 |
