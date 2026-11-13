# Charter Package Format 1.0 (Public Review Draft)

**Public review draft of version 1.0, [DATE]. Editor: Seed Machines. Comments are welcome; see section 21.**

Companion files: `charter-package-format-1.0.schema.json` (JSON Schema), `validate.py` (reference validator), `tests/` (28 conformance test packages with `manifest.json`).

## 1. Scope

This specification defines the charter package: a sealed, versioned, machine-readable document that states, before an autonomous unit is deployed, what the unit may do (its capability envelope), how it is stopped when it leaves that envelope (its intervention hierarchy), who may authorize what (its authorization model), what it must record (its record schema), how its performance is reviewed and a version withdrawn (its operations review), and which party answers for which part (its sign-off).

The specification covers the format, the meaning of each part, how a package is sealed and versioned, and what it means for a package to conform.

This specification places requirements on packages and on software that writes, validates or reads them. It places no requirement on how a unit, a controller or a gate decides or acts.

It does not cover how a package is written, how a unit enforces it, or how a package or a record is reviewed, examined, verified or certified. It does not reproduce or replace any safety standard: a package names the standards it relies on (section 5), and a domain profile (section 19) may list them by title.

This version covers a package for one unit or one unit type.

## 2. Conformance language

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be read as described in RFC 2119 and RFC 8174 when, and only when, they appear in capitals.

## 3. Terms

- **Unit**: the autonomous system the package governs.
- **Producer**: software or a person that writes a package.
- **Consumer**: software that reads a package (section 18).
- **Signal**: a named, measured quantity that rules refer to.
- **Check**: a machine-evaluable rule over signals (section 7).
- **Stated rule**: a rule written in words that is not itself a check: a prohibited action, a required authorization, the contact protocol, an automated response or a resume condition (8.3).
- **Record**: the unit's log while running under a package.
- **Seal**: the SHA-256 digest that fixes a package's content (section 15).
- **Assumed**: a value the producer chose without confirmation from the responsible party.

## 4. Document model

A package is a single JSON object (RFC 8259, UTF-8). It MUST contain these sections:

| Section | Purpose | Defined in |
|---|---|---|
| `metadata` | Identity, version, status, parties, references, seal | 5 |
| `signals` | Dictionary of the quantities rules read | 6 |
| `capability_envelope` | Limits, zones, prohibited actions, checks, enforcement | 8 |
| `decision_tree` | Intervention hierarchy | 9 |
| `authorization_model` | Who may grant what, and the fixed evaluation rules | 10 |
| `record_schema` | What the record must hold and how it protects itself | 11 |
| `operations_review` | Performance targets, review schedule, rollback | 12 |
| `sign_off` | Parties, and which party owns each section | 13 |
| `risk_scenarios` | Which known risks the package addresses and which remain open | 14.1 |

It MAY contain `underwriting_requirements` and `regulatory_conditions` (14.2).

Every section except `metadata` and `risk_scenarios` carries its own `version` string, so a change to one section can be seen without comparing whole packages.

Consumers MUST ignore members they do not recognize. Extension data SHOULD go in a top-level member whose name begins with `x_`; such a member is a section for the purposes of sign-off (13) if it is an object. Members that the seal leaves out (section 15) are outside this specification.

## 5. Metadata

| Member | Rule |
|---|---|
| `package_id` | MUST match `CHARTER-` followed by upper-case segments, e.g. `CHARTER-WAREHOUSE-20261009-001`. `GOS-` ids from earlier producers remain valid. MUST NOT change between versions of the same package. |
| `version` | `major.minor` string. Each new version MUST have a higher number than the one it replaces. |
| `status` | `DRAFT`, `DRAFT-ASSUMED` (contains assumed values), `SAMPLE` (demonstration only), or `APPROVED`. A package containing any `"assumed": true` MUST be `DRAFT-ASSUMED` or `SAMPLE`. An `APPROVED` package MUST carry its `package_hash`. |
| `created_at` | RFC 3339 timestamp. |
| `domain`, `unit`, `operator` | Non-empty strings. |
| `insurer` | String or null. |
| `regulatory_references` | The standards and regulations relied on, by title. A reference to a paid standard SHOULD name the edition when known. |
| `supersedes`, `change_summary` | Optional: the version this one replaces, and the changes in words. |
| `seal_algorithm` | Names the canonical form and what the seal leaves out (section 15). |
| `package_hash` | Null until sealed; then the 64-character lower-case hex seal. |

## 6. Signals

`signals.items` lists the quantities checks, triggers and conditions read. Each item has:

- `id`: lower snake case, carrying its unit where it helps (`speed_mps`, `nearest_person_m`). The location signals are `zone` (string), `x_m` and `y_m`.
- `description`, `unit` (string or null), `type` (`number`, `string` or `boolean`).
- `source`: the sensor or log that produces it. SHOULD be non-empty.
- `rate_hz` and `max_age_s`: how often it is produced, and how long a reading stays current. If `max_age_s` is absent, a reading stays current for three periods of `rate_hz`.
- `assumed`: boolean.

A reading older than its `max_age_s` is **unknown**. It MUST NOT be treated as its last known value.

## 7. Check language

### 7.1 Check object

```json
{"signal": "speed_mps", "operator": "<=", "value": 0.8, "when": "zone in ['shared_aisle', 'pick_station']"}
```

- `signal`: a signal id.
- `operator`: one of `<`, `<=`, `>`, `>=`, `==`, `!=`, `in`, `not_in`.
- `value`: number, string or boolean; a list of these for `in` and `not_in`, and only for them.
- `when` (optional): a condition (7.2) under which the check applies.
- `for_seconds` (triggers only, optional): how long the condition must hold continuously before the trigger fires.

An envelope check is written so that it is **true while the unit is inside its envelope**. A trigger is written so that it is **true when the level should fire**.

### 7.2 Condition grammar

```
condition  = or
or         = and { ("||" | "or") and }
and        = not { ("&&" | "and") not }
not        = ("!" | "not") not | comparison
comparison = atom [ compare-op atom | ("!" | "not") "in" atom ]
compare-op = "==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "not_in"
atom       = number | string | "true" | "false" | "null"
           | signal-id | "(" or ")" | "[" [ atom { "," atom } ] "]"
number     = ["-"] digit+ ["." digit+]
string     = "'" chars "'" | '"' chars '"'
```

There are no function calls and no arithmetic. Every identifier is a signal id.

### 7.3 Evaluation with missing data

Evaluation uses three values: true, false and unknown. A comparison involving an unknown, null or empty reading is unknown. `&&` is false if either side is false, else unknown if either side is unknown. `||` is true if either side is true, else unknown if either side is unknown. `!` of unknown is unknown.

A consumer MUST report an unknown envelope check as **not shown to be within the envelope**, never as within it. A trigger that is unknown has **not been shown to fire**.

### 7.4 Combined triggers

A `trigger_check`, and only a `trigger_check`, MAY combine conditions instead of naming one signal. It then has exactly one of:

- `condition`: one expression in the grammar of 7.2;
- `any_of`: a list of at least two parts, read as joined by `||`;
- `all_of`: a list of at least two parts, read as joined by `&&`.

Each part of `any_of` or `all_of` is a condition string, a check object (7.1, whose own `when` applies to that part only), or another combined object. A combined trigger MUST NOT also carry `signal` or `operator`. It MAY carry `when` and `for_seconds`, which apply to the whole. Evaluation is three-valued as in 7.3: a part that cannot be decided never counts as met.

## 8. Capability envelope

### 8.1 Limits and zones

`capability_envelope` holds `performance` (including `max_speed_ms`, `max_payload_kg`, `max_altitude_m`, `additional_limits`), `spatial` (`permitted_zones`, `prohibited_zones`, `human_proximity` with `warning_distance_m`, `critical_distance_m`, `contact_protocol`), `prohibited_actions` and `authorization` (`required_for`, `authorized_by`).

### 8.2 Checks

`checks` MUST contain at least one entry. Each has a unique `id` of the form `ENV-nn`, a plain-language `rule`, a simple `check` object (7.1; combined forms are not allowed here), and `assumed`.

### 8.3 Enforcement

`capability_envelope.enforcement` and `decision_tree.enforcement` MAY list, for a stated rule, what enforces it:

```json
{"rule": "Changing any limit in this envelope", "by": "authorization", "ref": "tier 3"}
```

- `rule`: the stated rule, word for word as it appears in the package.
- `by`: `check` (a check or level trigger enforces it), `gate` (the unit's internal gate refuses it; prohibited actions only), `authorization` (it needs a grant at a consequence tier or reversibility class), or `record` (it is evidenced by a record event).
- `ref`: one reference or a list. For `check`, a check id or `level_N`; for `gate`, the literal `prohibited_actions`; for `authorization`, `tier N` or a reversibility class; for `record`, an event type in `record_schema.event_records`.

Every entry's `rule` and `ref` MUST resolve (R8).

## 9. Decision tree (intervention hierarchy)

`decision_tree.levels` lists at least three levels, numbered uniquely from 1. Each has `name`, a plain-language `trigger`, an optional `trigger_check` (7.1 or 7.4), an `automated_response`, and optionally `escalation_timeout_seconds`, `escalates_to`, `notify` and `resume_conditions` (a list of stated rules for leaving that level).

- `escalates_to` MUST name an existing level higher than the current one.
- At least one level MUST be named `fail_safe`, and it SHOULD be the last. It MUST list `resume_authorization`: who may let the unit resume. It MAY name a `fail_safe_location`.
- An escalation timeout MUST lead to a **more** restrictive level. A package MUST NOT state a timeout that relaxes a restriction.
- `based_on_templates` MAY list library template ids the tree was built from.

## 10. Authorization model

`authorization_model` defines how requests to act (from an operator console, an AI planner, a language interface, a vendor update, a learning system or a fleet manager, listed in `evaluated_sources`) are decided.

- `reversibility_classes`: `reversible` actions are handled `proceed_then_review` within `review_within_hours`; `irreversible` actions are handled `hold_declare_await`, and the package states `refuse_and_hold_safe_state` as the handling when no decision is received.
- `consequence_tiers`: numbered from 1, each with a description.
- `authority_classes`: each with unique `id`, `rank`, `holder` and `may_grant`. A class with id `unassigned`, null holder, empty `may_grant` and the highest rank MUST be present.
- `evaluation_rules`: these six members MUST appear **exactly** as follows. They are the fixed core of the format and are not configurable by a producer:

| Member | Required value |
|---|---|
| `outcomes` | `["granted", "refused", "referred", "unresolved"]` |
| `routing` | `Among the classes whose may_grant covers the tier and that hold the capability requested, the lowest-ranked one. Rank orders eligible classes; it never grants by itself.` |
| `missing_input` | `unresolved, never treated as permission` |
| `timeout` | `No timeout converts a request into a grant` |
| `unassigned_class` | `Requests above every assigned class rest as open; the unit continues existing permitted work` |
| `conflict` | `Unresolved conflicts drive the unit to its fail-safe state` |

Packages from earlier producers MAY instead carry the routing wording `Lowest-ranked class whose rank meets the tier and that holds the capability requested`. It is read with the meaning above. Producers MUST NOT write it in new packages.

## 11. Record schema and record integrity

`record_schema` states the record's `format` (JSON Lines is RECOMMENDED), `storage` (location, `retention_days`, access controls), `required_fields_per_entry`, `integrity`, `continuous_telemetry` (`frequency_hz`, `fields`), `event_records`, `configuration_change_records`, `authorization_records` and `forensic_decidability`.

- `required_fields_per_entry` MUST include `timestamp`, `event_type`, `package_hash`, `prev_entry_hash` and `entry_hash`.
- Each record entry carries the seal of the package in force (`package_hash`).
- Entries are hash-chained: `prev_entry_hash` is the previous entry's `entry_hash` (null for the first), and `entry_hash` is the SHA-256 of the entry serialized as compact JSON in the order its fields were written, without its `entry_hash` member.
- A time gap with an intact chain means the unit did not record. A broken chain means the record was changed after writing.
- `integrity.independent_copy` SHOULD say where a copy of the chain head is kept outside the unit.
- `forensic_decidability.questions_answerable` MUST list at least the seven post-incident questions in Annex A.

## 12. Operations review

`operations_review` says how the package is judged in use and how a version is withdrawn:

- `performance_targets`: at least one, each with a unique `id` and non-empty `metric`, `target`, `window`, `watched_by` and `if_missed`.
- `review`: `owner`, `cadence_days` (positive), and optionally `valid_from`, `valid_to`, `next_review` (dates; `valid_to` after `valid_from`) and `early_review_triggers`.
- `rollback`: `conditions` (at least one: when a version is withdrawn), `backout_plan`, `decided_by` (an assigned authority class id from section 10, never `unassigned`), optionally `fallback_version` (an earlier version, or null) and `notify`.

## 13. Sign-off

`sign_off` names the parties to the package and what each answers for:

- `parties`: each with a `role` (`developer`, `operator`, `insurer` or `risk_engineer`), and optionally `name` and `organization`. Each role appears at most once. The developer and the operator MUST be parties.
- `section_owners`: maps every other section of the package (every top-level object except `sign_off` and members the seal leaves out) to the role that owns it. Every such section MUST have an owner, every key MUST be a section present in the package, and every owner MUST be a listed party.

## 14. Risk scenarios and conditions from other parties

### 14.1 Risk scenarios

`risk_scenarios` names the scenario `library` used (or null) and lists scenarios `addressed` (with the envelope controls, intervention and record fields that cover each) and `open` (with the reason and what is needed). A scenario id is a library id of the form `XX-YYY-nnn`, or null for a scenario not in any library.

### 14.2 Underwriting requirements and regulatory conditions (optional)

`underwriting_requirements.items` records conditions and follow-ups raised by an insurer; `regulatory_conditions.items` records those raised by a certifier or regulator. Both carry provenance:

- `id` (`UR-nn` or `RC-nn`), `kind` (`condition` or `follow_up`), `requirement`, `raised_by` and `source` are copied **exactly** as received and MUST NOT change in later versions. Underwriting requirements carry `for_insured` and a source of `set_id` and `set_version`; regulatory conditions carry `for_applicant`, a source of `review_id` and `review_version`, and `raised_by.role` of `certifier` or `regulator`.
- `decision` is `accepted`, `declined` or `pending`. An accepted or declined item MUST name `decided_by` with `name` and `role`.
- `status` is `met`, `partly_met` or `not_met`, with `met_by` citing the package paths and values that meet it.
- An item present in one version MUST be present in every later version; a declined one stays, with its reason in `note`.

## 15. Sealing

The seal is the SHA-256 digest, as lower-case hex, of the package with `metadata.package_hash` set to null and without the top-level members `seal_algorithm.excludes` names, serialized in the canonical form it names:

```json
"seal_algorithm": {"canonicalization": "RFC 8785 (JCS)", "digest": "SHA-256", "excludes": "metadata.package_hash"}
```

`excludes` is a comma-separated list that begins with `metadata.package_hash` and MAY name top-level members holding evidence added after sealing; such members are outside this specification. A package without `seal_algorithm` (from the earliest producers) is sealed over its JSON indented with two spaces. A producer MUST include `seal_algorithm` in a new package and MUST NOT alter it in a sealed one.

The seal proves only that content is identical to what was sealed. It does not by itself show who approved the package or that a unit ran it.

## 16. Conformance

A package conforms to this specification if it is valid against `charter-package-format-1.0.schema.json` **and**:

- R1. Every `when` condition and every combined trigger parses under 7.2.
- R2. Envelope check ids are unique; decision tree level numbers are unique.
- R3. Every `escalates_to` names an existing, higher level.
- R4. Authority class ids are unique and `unassigned` has the highest rank.
- R5. A package with any assumed value has status `DRAFT-ASSUMED` or `SAMPLE`.
- R6. An `APPROVED` package carries `package_hash`.
- R7. Against its previous version: same `package_id`, higher `version`, and every underwriting requirement and regulatory condition kept with its `requirement`, `raised_by` and `source` unchanged.
- R8. Every enforcement entry names a stated rule word for word, and its `ref` resolves as 8.3 says; `gate` is used only for prohibited actions.
- R9. Performance target ids are unique; `valid_to` is after `valid_from`; `rollback.decided_by` is an assigned authority class; `fallback_version`, if set, is earlier than `version`.
- R10. Sign-off parties are unique by role; every section has an owner; every owner is a party; every owned key is a section.

Conformance shows that a package is well formed, sealed and versioned, and that any tool can read and check it. It does not show that the unit's rules are connected to its live signals and records. A package or tool that claims conformance MUST name the version of this specification.

**Conforming validator.** A validator conforms if, for each case in `tests/manifest.json`, it accepts or rejects the package as the manifest expects and reports the seal status (`not_sealed`, `valid`, `broken`) as expected. `validate.py` is the reference validator.

## 17. Versioning and change

A new version of a package keeps `package_id`, raises `metadata.version`, raises the `version` of each changed section, and is sealed afresh. Running a new version is a configuration change and SHOULD be recorded under `record_schema.configuration_change_records` by the unit when it begins running it.

## 18. Consumers

A consumer MUST report a package that does not conform as not conforming, and MUST cite package items by their ids (`ENV-nn`, `level_N`, `UR-nn`, `RC-nn`, `PT-nn`) in anything it outputs. A consumer that reviews a package (an insurer, certifier or regulator) raises conditions only through 14.2.

## 19. Domain profiles (informative)

A profile lists, for one domain, the signals a package is expected to define, typical checks, the scenario library, and the standards that govern the topic, by title only. Profiles do not quote or restate paid standards.

**Warehouse AMR profile 0.1 (sketch).** Expected signals: `speed_mps`, `nearest_person_m`, `stop_margin_m`, `contact_sensed`, `zone`, `payload_kg`, `safety_field_active`, `battery_pct`, `fleet_link_lost_s`, `fire_alarm_active_s`. Typical checks: speed caps overall, in shared zones and at intersections; proximity warning and critical distances; stopped on link loss and fire alarm; prohibited zones such as exit routes. Governing standards by title: ANSI/A3 R15.08 parts 1 to 3; ISO 3691-4; OSHA 29 CFR 1910.176 and 1910.178 (public). Values in a profile are starting defaults, never values attributed to a standard.

## 20. Relationship to other standards (informative)

- **UL 4600**: a package is operational evidence a UL 4600 safety case can cite.
- **ASTM F3269**: the envelope and intervention hierarchy correspond to safe boundaries and the recovery function.
- **IEEE 7009 and P7009.1**: the decision tree and authorization model give a data format for fail-safe interventions.
- **ANSI/A3 R15.08-3**: configuration change records, sign-off and the operations review give a format for management-of-change and periodic-review evidence.
- **NIST AI RMF, ISO/IEC 42001, EU AI Act**: the operations review and sign-off correspond to their monitoring, review and accountability expectations.

## 21. Status, comments and use

This is a public review draft. It may change before the final version 1.0.

Copyright 2026 [FULL LEGAL NAME]. All rights reserved, except that anyone may read, copy and share this draft unchanged, and use the schema, validator and test packages to evaluate it and test their own tools, for the purpose of reviewing it and commenting on it. No other licence, including any patent licence, is granted by this draft.

Seed Machines intends to publish the final version 1.0 under an open licence. Comments: open an issue at https://github.com/SeedMachines/charter-package-format/issues.

## 22. Future work

1. Record entry schema as its own normative section, with test records.
2. Signal types: type-check each check's `value` against its signal's declared `type`.
3. A `metadata.spec_version` member, so a package states the version it claims to conform to.

## Annex A. Post-incident questions

1. What was the unit authorized to do at the moment of the incident?
2. What was the unit actually doing at the moment of the incident?
3. Who authorized the last configuration change, and when?
4. Was the unit operating within its approved capability envelope?
5. Were proximity rules in effect and functioning?
6. What was the intervention response sequence?
7. Was each action the AI initiated within its authorization, and who approved any change?
