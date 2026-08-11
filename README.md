# HWRS 564a — Hydrogeologic Analysis Tools & Methods I

Course materials for Fall 2026. University of Arizona, Department of
Hydrology & Atmospheric Sciences.

**Site:** <https://hwrs564-hydrogeologic-analysis.github.io/hwrs564a_course_materials/>

---

## For students

Click **Code → Codespaces → Create codespace on main**. Wait about two minutes
while `postbuild.sh` builds the Python environment, downloads the MODFLOW
binaries, and registers the Jupyter kernel.

Then open a notebook from `labs/` and select the **Python 3 (hwrs564a)** kernel.

Nothing to install on your own machine. If your codespace ends up in a broken
state, delete it and make a new one — that is what they are for.

---

## Repository layout

```
├── _quarto.yml            Project config: site nav, formats, theme
├── index.qmd              Course home page
├── slides/                One .qmd per class session
│   └── _metadata.yml      Shared slide config (live-revealjs, pyodide packages)
├── labs/                  In-class notebooks, by week
├── homework/              Graded assignments, released separately
├── quizzes/               Quiz questions as YAML + the D2L CSV generator
├── d2l/                   D2L page template, per-week YAML, and generator
├── data/                  Datasets — one place, not scattered per week
├── assets/                Figures, cheat sheets, logos
├── theme/ua.scss          UA brand styling for slides and site
└── .devcontainer/         Codespace definition
```

---

## For the instructor

### First-time setup

Steps 1–3 are **done** — the extension is in `_extensions/`, `uv.lock` is
committed, and Week 2 has been rendered and checked in a browser. Step 4 still
needs running once, against the real GitHub repo.

```bash
# 1. Quarto CLI — single binary, no Python conflicts
#    https://quarto.org/docs/get-started/
quarto --version

# 2. The quarto-live extension. This is what provides the `live-revealjs` and
#    `live-html` formats; without it every render fails with "Unknown format".
#    Note the repo is `quarto-live` but it installs to _extensions/r-wasm/live/.
quarto add r-wasm/quarto-live
git add _extensions && git commit -m "Add quarto-live extension"

# 3. Lock the Python environment. Commit the lockfile — otherwise every
#    codespace and CI run re-resolves and students get different versions.
uv sync
git add uv.lock && git commit -m "Pin dependencies"

# 4. Initialize gh-pages publishing. Creates _publish.yml, which the GitHub
#    Action needs. Run once, locally.
quarto publish gh-pages
git add _publish.yml && git commit -m "Configure gh-pages publishing"
```

Then confirm the whole thing works:

```bash
quarto preview slides/week02_tue_getting_started.qmd
```

**What to check on that first preview**, in order of likelihood of being wrong:

1. **Are hints and solutions hidden until clicked?** quarto-live hides them with
   Bootstrap's `.d-none`, which revealjs doesn't load. `theme/ua.scss` ships a
   shim for this — if hints are visible from the start, the shim isn't matching
   and needs adjusting.
2. Does the *Run Code* button appear in UA red, and does the editor look like an
   editor rather than unstyled HTML?
3. Do the MathJax equations render ($q = -K\,dh/dl$ on the Darcy slide)?
4. Does the matplotlib plot on the last content slide draw?

### Working on slides

```bash
quarto preview slides/week02_tue_getting_started.qmd   # live reload
quarto render                                          # build the whole site
```

Interactive code blocks use ```` ```{pyodide} ```` and run in the student's
browser via WebAssembly. Exercises take a label and support hints and solutions:

````markdown
```{pyodide}
#| setup: true
#| exercise: ex_gradient
head_upstream = 412.5
```

```{pyodide}
#| exercise: ex_gradient
gradient = ______
```

::: {.hint exercise="ex_gradient"}
The head drop divided by the distance.
:::
````

Blanks are **six or more underscores**. Exercises do not auto-run — the student
presses *Run Code*.

### MODFLOW conventions (Weeks 10–14)

Every MODFLOW notebook and deck follows the same four rules, and the labs repeat
them rather than hiding them in a helper:

```python
MF_EXE = ROOT / "modflow" / "mf2005"
assert MF_EXE.exists(), f"... run ./postbuild.sh from a terminal."

WS = ROOT / "_run" / "weekNN_name"          # gitignored, one per model
WS.mkdir(parents=True, exist_ok=True)

success, buff = mf.run_model(silent=True, report=True)
assert success, "MODFLOW did not converge:\n" + "\n".join(buff[-20:])
```

**`report=True` is not optional.** With `silent=True` alone FloPy returns an
**empty** `buff`, so the assertion above fires with no diagnostic in it — at
exactly the moment you needed one. The playbook's §1.8 snippet omits it; that is
a bug in the playbook, not in FloPy.

Three more things the labs establish and later weeks rely on:

- `top` and `botm` are **elevations**, not thicknesses.
- A **constant head sits at the cell centre**, so the flow path is one cell
  shorter than the domain. Ignoring this makes a modelled gradient 5% wrong on a
  20-column grid.
- **Recharge on a constant-head cell is discarded** — `RCH` applies only where
  `ibound > 0`.

**Pyodide cannot run MODFLOW.** `numpy`, `pandas`, `matplotlib`, and `scipy` work
in the browser, but MODFLOW is a compiled binary. For Weeks 10–14, slides use
pre-rendered figures (ordinary ```` ```{python} ```` blocks, executed at render
time) and the live FloPy work stays in Codespaces notebooks.
`slides/week11_tue_inputs_outputs.qmd` is the worked example: it builds, runs,
and maps a steady-state model during `quarto render`. Building those decks
requires the MODFLOW binaries, so run `./postbuild.sh` first.

Non-MODFLOW parts of those weeks — unit conversions, array arithmetic, plotting
a hardcoded head field — should still use live ```` ```{pyodide} ```` cells.
Don't drop interactivity just because the solver can't run in a browser.

**A generated figure must be a cell *output*, not a side-effect file.** Freeze
caches what a cell returns, not files it writes. A `{python}` block that saves
a PNG and a separate `![](...)` link to it works on the first render and breaks
on every cached one — the file is never recreated. Display the image from
inside the cell instead (`IPython.display.Image`), as
`slides/week09_thu_chemistry.qmd` does.

**Freeze.** `slides/_metadata.yml` sets `execute: freeze: auto`, so a deck only
re-executes when its own source changes. Two things to know:

- **`_freeze/slides/` must be committed.** Without it, CI starts cold and
  re-solves every model on every push. (`_freeze/site_libs/` is gitignored —
  Quarto regenerates those 5 MB of vendored JS on every render, and the cache
  works fine without them.)
- **Freeze only applies to *project* renders.** `quarto render` honours it;
  `quarto render slides/week11_tue_inputs_outputs.qmd` re-executes that file
  every time. That is usually what you want while authoring.

### Building quizzes

Questions live in `quizzes/weekNN.yml`. Generate the D2L import file:

```bash
python quizzes/build_d2l_csv.py quizzes/week03.yml
# -> quizzes/build/week03_d2l_import.csv
```

In D2L: **Quizzes → Add/Edit Questions → Import → Upload a File**.

Supported types: `mc`, `ms`, `tf`, `sa`, `wr`. Backticked `code`, `**bold**`, and
`*italic*` are converted to HTML with the flag column set automatically.

A week's quiz covers the **previous** week's material, so `quizzes/week04.yml`
is the quiz given at the start of Week 4 on what happened in Week 3.

### Building D2L content pages

Page content lives in `d2l/weeks/weekNN.yml`; the layout lives in
`d2l/template.html`.

```bash
python d2l/generate.py d2l/weeks/week02.yml          # write the page
python d2l/generate.py d2l/weeks/*.yml --check       # lint only
```

Every bullet must carry exactly one of five link forms — `url`,
`url` + `site_relative: true`, `course_file`, `dropbox`, or `quiz` — and the
linter rejects an item with none of them.

It also fails the build on the other failure modes that actually happened in
2025: a missing section or a title whose week number disagrees with the file.

A `dropbox` or `quiz` rcode written as `TBD-...` is a deliberate placeholder for
a D2L object that doesn't exist yet. The page still generates so you can review
it, and the linter prints a loud reminder — a dead quicklink looks like a
working link right up until a student clicks it.

### Lab notebooks and their solutions

There is **one file per lab**, not two. The answers live in the notebook's own
metadata under a `solutions:` key mapping exercise number → code, and the
filled-in copy is generated:

```bash
python scripts/fill_solutions.py labs/week02/week02_lab_python_basics.ipynb
# -> labs/week02/_solutions/week02_lab_python_basics.ipynb   (gitignored)
```

Because it is generated it cannot drift, and the script fails loudly if a
`YOUR TURN` cell has no answer or an answer has no cell. Everything after the
`# YOUR TURN` marker line is replaced, so any givens written above it survive.

Upload the generated copy to D2L after the session.

### Datasets

Everything in `data/` is committed, so no lab depends on someone else's uptime.
It is also *generated*, so it has provenance rather than being a magic CSV:

```bash
python scripts/fetch_data.py --list    # what gets built
python scripts/fetch_data.py           # rebuild it (needs network)
```

| File | What it is |
|---|---|
| `tucson_basin_wells.csv` | 1,693 USGS monitoring wells, Tucson basin |
| `tucson_water_levels.csv` | 9,046 measurements, 1922–2026, 80 best-monitored wells |
| `cache/nwis_09484000_dv.csv` | Sabino Creek daily discharge — the Week 6 offline fallback |
| `week04_permeameter.xlsx` | Constant-head permeameter runs; the one `read_excel` demo |
| `tucson_chemistry.csv` | 42 complete major-ion analyses, 1964–1992 (Week 9 Piper diagrams) |
| `tucson_grid_top.csv` | Land surface on the 40×60 model grid, m (Weeks 11–14) |

Two things worth knowing:

- **`dataretrieval` moved.** As of 1.2.0 `nwis.get_gwlevels` is gone and
  `nwis.get_record` is deprecated; groundwater levels now come from
  `dataretrieval.waterdata.get_field_measurements`. Week 6 should teach the
  `waterdata` API, not the one in older tutorials.
- Anything over ~10 MB should be fetched with `pooch` and a hash, not committed.
  Nothing here is close.
- **The chemistry build is slow.** The USGS samples endpoint times out on a
  bbox query over the whole basin, so `build_chemistry` walks the site list in
  chunks of 40. That is why the result is committed.
- **`tucson_grid_top.csv` is a fitted trend surface, not a DEM.** Interpolating
  the well elevations directly gives 8 m of relief between adjacent 250 m cells —
  survey scatter, not topography, and steep enough to make a MODFLOW `top` that
  dries cells immediately. The second-order fit captures basin form (rising
  south-east) with an RMSE of about 36 m over a 760 m spread. Fine for teaching,
  not fine for anything else.

### Checking your work

```bash
python scripts/check_slides.py slides/*.qmd       # exercise/hint wiring, blanks, divs
python d2l/generate.py d2l/weeks/*.yml --check    # D2L page lint
python d2l/generate_assignments.py d2l/assignments/hw*.yml --check
python scripts/fill_solutions.py labs/*/*.ipynb   # regenerate the runnable copies
pytest labs/                                      # execute them top-to-bottom
```

`pytest` runs the notebooks through [nbmake](https://github.com/treebeardtech/nbmake)
in a clean kernel, so a lab that only works when run out of order fails the
build. It collects **only** the generated `_solutions/` copies — the student
versions have `...` placeholders and are not meant to execute
(see `labs/conftest.py`).

All of these run in CI on every push, so a deck with a hint pointing at a
nonexistent exercise, or a lab whose CHECK cell expects the wrong number, fails
the build instead of reaching students.

Install the commit hooks once, so notebook outputs never get committed:

```bash
uv run pre-commit install
```

### Publishing

Pushing to `main` triggers `.github/workflows/publish.yml`, which lints the D2L
YAML, builds the quiz CSVs, renders the site, and pushes to `gh-pages`.

**One-time setup before the action will work:** run

```bash
quarto publish gh-pages
```

locally once. It creates `_publish.yml`, which the action needs, and configures
the `gh-pages` branch.

---

## Conventions

- Slides: `slides/weekNN_<day>_<topic>.qmd`
- Labs: `labs/weekNN/weekNN_lab_<topic>.ipynb`
- Homework prompt source: `homework/hwNN_<topic>.md`
- D2L assignment settings: `d2l/assignments/hwNN.yml`
- Quizzes: `quizzes/weekNN.yml`
- D2L pages: `d2l/weeks/weekNN.yml`

Two-digit week numbers throughout, so alphabetical order matches teaching order.

Datasets go in `data/` and are referenced by relative path — never committed
twice into per-week folders.

---

## License

See [LICENSE](LICENSE). Course content is provided for educational use.
