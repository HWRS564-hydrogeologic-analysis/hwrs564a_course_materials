# If you get lost

HWRS 564a uses three connected locations. They serve different purposes:

| Location | What it is for | Address |
|---|---|---|
| D2L | Official announcements, assignment instructions, submissions, quizzes, and grades | [HWRS 564a D2L course](https://d2l.arizona.edu/d2l/home/1779485) |
| GitHub repository | Editable source for the course website, labs, slides, D2L pages, and homework prompts | [hwrs564a_course_materials](https://github.com/HWRS564-hydrogeologic-analysis/hwrs564a_course_materials) |
| Course website | Published student-facing slides, labs, schedule, and reference material | [HWRS 564a course website](https://hwrs564-hydrogeologic-analysis.github.io/hwrs564a_course_materials/) |

D2L requires a University of Arizona login. The course website is public. The
GitHub repository is the source of truth for course content, but D2L remains the
source of truth for grades, submission status, and official deadlines.

## Local repository

On the current planning computer, the repository is located at:

```text
/Users/bzq/Documents/teaching/hwrs564a/f2026_planning/2026_repo/hwrs564a_course_materials
```

Run repository commands from that directory.

## Where to edit D2L material

| Material | Source location |
|---|---|
| Weekly D2L modules | `d2l/weeks/weekNN.yml` |
| Shared weekly-module layout | `d2l/template.html` |
| Homework instructions, settings, and rubrics | `d2l/assignments/hwNN.md` |
| Homework HTML layout | `d2l/assignment_template.html` |

Generate and validate the weekly module pages with:

```bash
python d2l/generate.py d2l/weeks/*.yml
python d2l/generate.py d2l/weeks/*.yml --check
```

Generate and validate the D2L assignment instructions with:

```bash
python d2l/generate_assignments.py d2l/assignments/hw*.md
python d2l/generate_assignments.py d2l/assignments/hw*.md --check
```

Generated HTML is placed in `d2l/build/`. That directory is ignored by Git and
should not be edited by hand. Upload the generated weekly page to the matching
D2L module, or paste the generated assignment HTML into the D2L Assignment's
Instructions field.

The D2L course org-unit ID used by the generators is `1779485`. Values such as
`TBD-hw03-dropbox` are placeholders; replace them with the real D2L rcode after
creating the associated assignment or quiz.

## Where to edit the GitHub repository

The remote repository is:

```text
https://github.com/HWRS564-hydrogeologic-analysis/hwrs564a_course_materials
```

Important source locations include:

- `index.qmd` — public course homepage and schedule
- `_quarto.yml` — website navigation and rendering configuration
- `slides/` — lecture slides
- `labs/` — student lab notebooks
- `data/` — shared course datasets
- `homework/` — assignment planning and design notes
- `d2l/assignments/` — complete Markdown homework sources
- `d2l/` — D2L templates, definitions, and generators
- `quizzes/` — quiz definitions and D2L import generator

Pushes to `main` trigger the publishing workflow in
`.github/workflows/publish.yml`.

## Where to edit the course website

The published site is:

```text
https://hwrs564-hydrogeologic-analysis.github.io/hwrs564a_course_materials/
```

Do not edit the published site directly. Edit `index.qmd`, `_quarto.yml`, the
slide sources, or the lab notebooks in the Git repository, then render locally:

```bash
quarto render
```

The local rendered site is written to `_site/`, which is generated and should
not be edited or committed. Publishing is handled from the repository's `main`
branch.

## Quick decision guide

- A grade or submission is wrong: fix it in **D2L**.
- A deadline appears incorrectly on the public schedule: edit `index.qmd` and
  the relevant `d2l/weeks/weekNN.yml` file.
- A slide, lab, dataset, or homework prompt is wrong: edit it in the **GitHub
  repository**, validate it, and publish or upload the regenerated result.
- The public website looks stale: confirm the change reached `main` and inspect
  the GitHub Actions publishing workflow.
- A D2L link contains `TBD-...`: create the D2L object and replace the
  placeholder with its real rcode.
