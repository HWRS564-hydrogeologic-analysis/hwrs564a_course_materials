# D2L assignment setup

Each Markdown file is a complete assignment source containing the student
instructions. Generated PDF copies live in `d2l/build/assignments/`.

Generate or validate the assignment descriptions from the repository root:

```bash
python d2l/generate_assignments.py d2l/assignments/hw*.md
python d2l/generate_assignments.py d2l/assignments/hw*.md --check
```

For each assignment in D2L:

1. Create a new **Individual assignment** in the Homework category.
2. Copy the title, score, availability, submission, and attempt settings from
   the assignment source and course plan.
3. Upload or link the corresponding generated PDF as appropriate.
4. Create the analytic rubric from the assignment criteria and attach it to the
   assignment.
5. Do not attach a starter notebook. Students create and submit their own
   `.ipynb` file.
6. Test the assignment in learner view, including the data path and filename.
7. Replace the `TBD-...` dropbox rcode in the weekly page YAML after the D2L
   object exists.

The generator builds content only; it does not create or modify a live D2L
course object.
