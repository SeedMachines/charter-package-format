# Charter Package Format 1.0 (Public Review Draft)

A charter package is a sealed, versioned, machine-readable document that states, before an autonomous machine is deployed, what it may do, how it is stopped when it leaves those limits, who may authorize what, what it must record, how its performance is reviewed, and which party answers for which part.

This repository holds the format so that anyone can write, read and check a charter package without depending on any one tool.

| File | What it is |
|---|---|
| `charter-package-format-1.0.md` | The specification |
| `charter-package-format-1.0.schema.json` | JSON Schema (draft 2020-12) |
| `validate.py` | Reference validator: `python3 validate.py package.json [previous_version.json]` (needs `pip install jsonschema`) |
| `tests/` | 28 conformance test packages and `manifest.json` with the expected result for each |

A validator conforms if it gives the result `tests/manifest.json` expects for every test package.

**Status.** Public review draft. Read, share and test it; see `NOTICE.md` and section 21 of the specification for what the draft allows. Seed Machines intends to publish the final 1.0 under an open licence.

**Comments.** Open an issue in this repository. Seed Machines edits the format; the Charter Package Builder (https://charter.seedmachines.ai) is one tool that produces it.
