#!/usr/bin/env python3
"""Reference validator for the Charter Package Format 1.0, public review draft.

Usage: python3 validate.py package.json [previous_version.json]

Checks the JSON Schema (structure), then the conformance rules R1 to R10
(section 16), then reports the seal. Exit code 0 if the package conforms.
"""
import hashlib, json, math, re, sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / 'charter-package-format-1.0.schema.json').read_text())

TOKEN = re.compile(r"\s*(?:(-?\d+(?:\.\d+)?)|('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")|(&&|\|\||==|!=|<=|>=|<|>|!|\(|\)|\[|\]|,)|([A-Za-z_][A-Za-z0-9_.]*))")
KEYWORDS = {'and', 'or', 'not', 'in', 'not_in', 'true', 'false', 'null'}
COMPARE = {'==', '!=', '<', '<=', '>', '>=', 'in', 'not_in'}


def parse_condition(src):
    """Parse a `when` condition (section 7). Returns the signal ids it reads; raises ValueError."""
    toks, pos, src = [], 0, str(src)
    while pos < len(src):
        if not src[pos:].strip():
            break
        m = TOKEN.match(src, pos)
        if not m:
            raise ValueError(f'unreadable near "{src[pos:pos + 12].strip()}"')
        pos = m.end()
        if m.group(1) is not None or m.group(2) is not None:
            toks.append(('lit', None))
        elif m.group(3) is not None:
            toks.append(('op', m.group(3)))
        else:
            w = m.group(4)
            lw = w.lower()
            if lw in ('and', 'or', 'not'):
                toks.append(('op', {'and': '&&', 'or': '||', 'not': '!'}[lw]))
            elif lw in ('in', 'not_in'):
                toks.append(('op', lw))
            elif lw in ('true', 'false', 'null'):
                toks.append(('lit', None))
            else:
                toks.append(('id', w))
    ids, i = set(), 0

    def is_op(v, k=0):
        return i + k < len(toks) and toks[i + k] == ('op', v)

    def p_or():
        nonlocal i
        p_and()
        while is_op('||'):
            i += 1; p_and()

    def p_and():
        nonlocal i
        p_not()
        while is_op('&&'):
            i += 1; p_not()

    def p_not():
        nonlocal i
        if is_op('!') and not is_op('in', 1):
            i += 1; p_not(); return
        p_cmp()

    def p_cmp():
        nonlocal i
        p_atom()
        if i < len(toks) and toks[i][0] == 'op' and toks[i][1] in COMPARE:
            i += 1; p_atom()
        elif is_op('!') and is_op('in', 1):
            i += 2; p_atom()

    def p_atom():
        nonlocal i
        if i >= len(toks):
            raise ValueError('ends too early')
        t, v = toks[i]; i += 1
        if t == 'lit':
            return
        if t == 'id':
            ids.add(v); return
        if (t, v) == ('op', '('):
            p_or()
            if not is_op(')'):
                raise ValueError('missing )')
            i += 1; return
        if (t, v) == ('op', '['):
            if is_op(']'):
                i += 1; return
            while True:
                p_atom()
                if is_op(','):
                    i += 1; continue
                if is_op(']'):
                    i += 1; return
                raise ValueError('missing ]')
        raise ValueError(f'unexpected "{v}"')

    p_or()
    if i != len(toks):
        raise ValueError(f'unexpected "{toks[i][1]}"')
    return ids


def js_number(x):
    """Write a number as ECMAScript's JSON serializer does (RFC 8785 section 3.2.2.3)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError('A number in the package cannot be written as JSON.')
        if x == int(x) and abs(x) < 1e21:
            return str(int(x))
        r = repr(x)
        if 'e' in r:
            mant, exp = r.split('e')
            exp = int(exp)
            if -7 < exp < 21:
                return format(x, 'f').rstrip('0').rstrip('.')
            return f"{mant}e{'+' if exp > 0 else '-'}{abs(exp)}"
        return r
    return str(x)


def canonical(v):
    """RFC 8785 (JCS) canonical JSON."""
    if v is None or isinstance(v, bool) or isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (int, float)):
        return js_number(v)
    if isinstance(v, list):
        return '[' + ','.join(canonical(x) for x in v) + ']'
    keys = sorted(v.keys(), key=lambda k: k.encode('utf-16-be'))
    return '{' + ','.join(json.dumps(k, ensure_ascii=False) + ':' + canonical(v[k]) for k in keys) + '}'


def excluded_members(pkg):
    """Section 15: top-level members named in seal_algorithm.excludes after metadata.package_hash."""
    ex = str(((pkg.get('metadata') or {}).get('seal_algorithm') or {}).get('excludes', ''))
    return [x.strip() for x in ex.split(',') if x.strip() and '.' not in x.strip()]


def seal(pkg):
    meta = dict(pkg.get('metadata') or {})
    stored = meta.get('package_hash')
    meta['package_hash'] = None
    unsealed = {**pkg, 'metadata': meta}
    for name in excluded_members(pkg):
        unsealed.pop(name, None)
    if re.search(r'8785|JCS', str((meta.get('seal_algorithm') or {}).get('canonicalization', '')), re.I):
        text, method = canonical(unsealed), 'rfc8785'
    else:
        text, method = json.dumps(unsealed, indent=2, ensure_ascii=False), 'legacy_two_space'
    computed = hashlib.sha256(text.encode('utf-8')).hexdigest()
    status = 'not_sealed' if not stored else ('valid' if stored == computed else 'broken')
    return {'computed': computed, 'stored': stored, 'method': method, 'status': status}


def any_assumed(o):
    if isinstance(o, dict):
        return o.get('assumed') is True or any(any_assumed(x) for x in o.values())
    if isinstance(o, list):
        return any(any_assumed(x) for x in o)
    return False


def version_number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def literal(v):
    if isinstance(v, list):
        return '[' + ', '.join(literal(x) for x in v) + ']'
    if isinstance(v, str):
        return "'" + v.replace('\\', '\\\\').replace("'", "\\'") + "'"
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return 'null' if v is None else js_number(v)


def compound_expr(c):
    """Section 7.4: a combined trigger as one condition, or None for a simple check."""
    if not isinstance(c, dict):
        return None
    if isinstance(c.get('condition'), str):
        return c['condition']
    if isinstance(c.get('any_of'), list):
        items, op = c['any_of'], ' || '
    elif isinstance(c.get('all_of'), list):
        items, op = c['all_of'], ' && '
    else:
        return None
    parts = []
    for x in items:
        if isinstance(x, str):
            parts.append(f'({x})'); continue
        inner = compound_expr(x)
        if inner is not None:
            parts.append(f'({inner})'); continue
        x = x if isinstance(x, dict) else {}
        cmp = f"{x.get('signal')} {x.get('operator')} {literal(x.get('value'))}"
        parts.append(f"(({x['when']}) && {cmp})" if x.get('when') else f'({cmp})')
    return op.join(parts)


def collect_checks(pkg):
    out = [{'id': c['id'], 'rule': c.get('rule', ''), 'kind': 'envelope', 'check': c['check']}
           for c in pkg['capability_envelope']['checks']]
    out += [{'id': f'level_{l["level"]}', 'rule': l.get('trigger', ''), 'kind': 'trigger', 'check': l['trigger_check']}
            for l in pkg['decision_tree']['levels'] if 'trigger_check' in l]
    return out


def prose_rules(pkg):
    """Section 8.3: rules stated in words that are not themselves checks."""
    ce, out = pkg['capability_envelope'], []
    out += [(t, 'prohibited') for t in ce.get('prohibited_actions', []) if isinstance(t, str)]
    out += [(t, 'authorization') for t in ce.get('authorization', {}).get('required_for', []) if isinstance(t, str)]
    cp = ce.get('spatial', {}).get('human_proximity', {}).get('contact_protocol')
    if isinstance(cp, str):
        out.append((cp, 'protocol'))
    for l in pkg['decision_tree']['levels']:
        if isinstance(l.get('automated_response'), str) and l['automated_response'].strip():
            out.append((l['automated_response'], 'response'))
        out += [(t, 'resume') for t in l.get('resume_conditions', []) if isinstance(t, str)]
    return out


def enforcement_list(pkg):
    return [e for e in pkg['capability_envelope'].get('enforcement', []) + pkg['decision_tree'].get('enforcement', []) if isinstance(e, dict)]


def parse_ids(src):
    if not src:
        return set()
    try:
        return parse_condition(src)
    except ValueError:
        return set()


def check_rules(pkg, previous=None):
    """Section 16, rules R1 to R10. Returns a list of problems."""
    problems = []

    def parse(where, src):
        try:
            parse_condition(src)
        except ValueError as e:
            problems.append(f'R1: {where} has a condition that does not parse ({e}).')

    def check_rule(where, c):
        expr = compound_expr(c)
        if expr is not None:
            parse(where, expr)
        if 'when' in c:
            parse(where, c['when'])

    seen = set()
    for c in pkg['capability_envelope']['checks']:
        if c['id'] in seen:
            problems.append(f'R2: check id "{c["id"]}" is used twice.')
        seen.add(c['id'])
        check_rule(c['id'], c['check'])

    levels = pkg['decision_tree']['levels']
    numbers = [l['level'] for l in levels]
    if len(set(numbers)) != len(numbers):
        problems.append('R2: decision tree level numbers must be unique.')
    for l in levels:
        if 'trigger_check' in l:
            check_rule(f'level {l["level"]} trigger_check', l['trigger_check'])
        if 'escalates_to' in l:
            if l['escalates_to'] not in numbers:
                problems.append(f'R3: level {l["level"]} escalates to level {l["escalates_to"]}, which does not exist.')
            elif l['escalates_to'] <= l['level']:
                problems.append(f'R3: level {l["level"]} escalates to level {l["escalates_to"]}; escalation must go to a higher level.')

    am = pkg['authorization_model']
    ids = [c['id'] for c in am['authority_classes']]
    if len(set(ids)) != len(ids):
        problems.append('R4: authority class ids must be unique.')
    ranks = {c['id']: c['rank'] for c in am['authority_classes']}
    if any(r >= ranks.get('unassigned', 0) for k, r in ranks.items() if k != 'unassigned'):
        problems.append('R4: the "unassigned" authority class must have the highest rank.')

    meta = pkg['metadata']
    status = meta['status']
    if any_assumed(pkg) and status not in ('DRAFT-ASSUMED', 'SAMPLE'):
        problems.append('R5: some values are marked assumed, so metadata.status must be "DRAFT-ASSUMED".')
    if status == 'APPROVED' and not meta.get('package_hash'):
        problems.append('R6: an APPROVED package must carry its package_hash.')

    # R8: enforcement entries name a stated rule and something that exists
    rules = dict(prose_rules(pkg))
    check_ids = {c['id'] for c in collect_checks(pkg)}
    events = set(pkg['record_schema'].get('event_records', []))
    tiers = {f'tier {t["tier"]}' for t in am['consequence_tiers']}
    classes = {c['class'] for c in am['reversibility_classes']}
    for i, e in enumerate(enforcement_list(pkg), 1):
        where = f'enforcement entry {i} ("{e["rule"][:50]}")'
        if e['rule'] not in rules:
            problems.append(f'R8: {where} names a rule that is not stated in the package word for word.'); continue
        for ref in (e['ref'] if isinstance(e['ref'], list) else [e['ref']]):
            if e['by'] == 'check' and ref not in check_ids:
                problems.append(f'R8: {where} refers to check "{ref}", which does not exist.')
            if e['by'] == 'record' and ref not in events:
                problems.append(f'R8: {where} refers to "{ref}", which is not in record_schema.event_records.')
            if e['by'] == 'authorization' and ref not in tiers and ref not in classes:
                problems.append(f'R8: {where} refers to "{ref}", which is not a consequence tier or reversibility class.')
            if e['by'] == 'gate' and ref != 'prohibited_actions':
                problems.append(f'R8: {where} is enforced by the gate, so its ref must be "prohibited_actions".')
        if e['by'] == 'gate' and rules[e['rule']] != 'prohibited':
            problems.append(f'R8: {where} is enforced by the gate, which refuses prohibited actions only.')

    # R9: operations review
    ops = pkg['operations_review']
    tids = [t['id'] for t in ops['performance_targets']]
    if len(set(tids)) != len(tids):
        problems.append('R9: performance target ids must be unique.')
    rv = ops['review']
    if rv.get('valid_from') and rv.get('valid_to') and rv['valid_to'] <= rv['valid_from']:
        problems.append('R9: operations_review.review.valid_to must be after valid_from.')
    rb = ops['rollback']
    if rb['decided_by'] not in ids or rb['decided_by'] == 'unassigned':
        problems.append(f'R9: operations_review.rollback.decided_by "{rb["decided_by"]}" must be an assigned authority class id.')
    if rb.get('fallback_version') is not None and not version_number(rb['fallback_version']) < version_number(meta['version']):
        problems.append(f'R9: rollback.fallback_version {rb["fallback_version"]} must be earlier than {meta["version"]}.')

    # R10: sign-off
    so = pkg['sign_off']
    roles = [p['role'] for p in so['parties']]
    if len(set(roles)) != len(roles):
        problems.append('R10: sign_off.parties lists a role more than once.')
    outside = {'sign_off', *excluded_members(pkg)}
    owned = [k for k, v in pkg.items() if k not in outside and isinstance(v, dict)]
    owners = so['section_owners']
    for k in owned:
        if k not in owners:
            problems.append(f'R10: sign_off.section_owners does not name an owner for "{k}".')
    for k, r in owners.items():
        if k not in owned:
            problems.append(f'R10: sign_off.section_owners names "{k}", which is not a section of this package.')
        if r not in roles:
            problems.append(f'R10: section "{k}" is owned by "{r}", which is not a party.')

    # R7: version sequence and kept provenance
    if previous:
        pm = previous['metadata']
        if pm['package_id'] != meta['package_id']:
            problems.append(f'R7: package_id changed from {pm["package_id"]} to {meta["package_id"]}.')
        elif not version_number(meta['version']) > version_number(pm['version']):
            problems.append(f'R7: version {meta["version"]} does not follow the previous version {pm["version"]}.')
        for sec in ('underwriting_requirements', 'regulatory_conditions'):
            new = {x['id']: x for x in (pkg.get(sec) or {}).get('items', [])}
            for k in (previous.get(sec) or {}).get('items', []):
                x = new.get(k['id'])
                if not x:
                    problems.append(f'R7: {k["id"]} was in the previous version but is missing from {sec}.'); continue
                for f in ('requirement', 'raised_by', 'source'):
                    if f in k and x.get(f) != k[f]:
                        problems.append(f'R7: {k["id"]} must keep its {f} exactly as recorded.')

    return problems


def validate(pkg, previous=None):
    v = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker())
    errors = sorted(v.iter_errors(pkg), key=lambda e: list(e.absolute_path))
    problems = [f'schema: {"/".join(map(str, e.absolute_path)) or "(root)"}: {e.message[:200]}' for e in errors]
    if not problems:
        problems = check_rules(pkg, previous)
    return problems


if __name__ == '__main__':
    args = sys.argv[1:]
    pkg = json.loads(Path(args[0]).read_text())
    prev = json.loads(Path(args[1]).read_text()) if len(args) > 1 else None
    problems = validate(pkg, prev)
    print('conforms' if not problems else 'does not conform')
    for p in problems:
        print('PROBLEM', p)
    s = seal(pkg)
    print(f'seal {s["status"]} ({s["method"]}): {s["computed"]}')
    sys.exit(1 if problems else 0)
