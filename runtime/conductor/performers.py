"""Domain performers, employment, execution sessions, skills, memory, effects and resolver handoffs.

One logical performer per domain is the stable identity; employment is the Human-agreed contract that binds it to
the domain; sessions and attempts are replaceable execution resources inside it. A session count, a model or an
attempt count is never a performer count. Every write here runs inside the caller's queue transaction, so the task
ledger, these facts and the outbox commit together and a queue ack follows them. Memory search indexes and UI
projections are rebuildable views; they never replace the ledger, recorded decisions or execution facts.

Undecided product policy is a reversible setting with an explicit default that enables nothing new: no automatic
deletion, no cross-domain sharing, no automatic skill publication, no external compensation and no forced
cancellation on replacement or skill revocation. Resolver models are never chosen here.
"""
from __future__ import annotations

import json
import math
import re

from storage.errors import ContractError

SCHEMA = '''
CREATE TABLE IF NOT EXISTS performers(id TEXT PRIMARY KEY, domain_id TEXT NOT NULL, name TEXT NOT NULL,
 created_at REAL NOT NULL, created_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS employments(id TEXT PRIMARY KEY, performer_id TEXT NOT NULL, domain_id TEXT NOT NULL,
 revision INTEGER NOT NULL, status TEXT NOT NULL, authority TEXT NOT NULL, skill_scope TEXT NOT NULL,
 decision_ref TEXT NOT NULL, actor TEXT NOT NULL, supersedes TEXT, created_at REAL NOT NULL, ended_at REAL,
 end_reason TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS employments_one_active ON employments(domain_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS exec_sessions(id TEXT PRIMARY KEY, owner_kind TEXT NOT NULL, owner_id TEXT NOT NULL,
 domain_id TEXT, tier TEXT NOT NULL, settings TEXT, state TEXT NOT NULL, current_attempt_id TEXT,
 created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS task_owners(delegation_id TEXT PRIMARY KEY, task_revision INTEGER NOT NULL,
 owner_epoch INTEGER NOT NULL, spec_hash TEXT NOT NULL, result_attempt_id TEXT);
CREATE TABLE IF NOT EXISTS assignment_log(seq INTEGER PRIMARY KEY AUTOINCREMENT, delegation_id TEXT UNIQUE NOT NULL,
 request_id TEXT NOT NULL, assignment_key TEXT, domain_id TEXT, conductor_id TEXT NOT NULL, slot TEXT,
 epoch INTEGER, turn_id TEXT, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS attempt_bindings(attempt_id TEXT PRIMARY KEY, delegation_id TEXT NOT NULL,
 task_revision INTEGER NOT NULL, owner_epoch INTEGER NOT NULL, tier TEXT NOT NULL, performer_id TEXT,
 employment_id TEXT, session_id TEXT, manifest_id TEXT, snapshot_id TEXT, claim_token TEXT, lease_until REAL,
 heartbeat_at REAL, not_before REAL, handoff_id TEXT, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS skill_revisions(id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, revision INTEGER NOT NULL,
 layer TEXT NOT NULL, scope_id TEXT, source_ref TEXT NOT NULL, content_hash TEXT NOT NULL, status TEXT NOT NULL,
 origin TEXT, actor TEXT NOT NULL, approval_ref TEXT, revoked_reason TEXT, created_at REAL NOT NULL,
 updated_at REAL NOT NULL, UNIQUE(skill_id, revision));
CREATE TABLE IF NOT EXISTS execution_manifests(id TEXT PRIMARY KEY, attempt_id TEXT UNIQUE NOT NULL,
 skills TEXT NOT NULL, authority TEXT NOT NULL, hash TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS memory_entries(id TEXT PRIMARY KEY, kind TEXT NOT NULL, scope_kind TEXT NOT NULL,
 scope_id TEXT NOT NULL, domain_id TEXT, text TEXT NOT NULL, source_ref TEXT NOT NULL, observed_at REAL NOT NULL,
 writer TEXT NOT NULL, confidence REAL, supersedes TEXT, contradiction TEXT NOT NULL, retention TEXT NOT NULL,
 status TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS memory_index(term TEXT NOT NULL, entry_id TEXT NOT NULL, PRIMARY KEY(term, entry_id));
CREATE TABLE IF NOT EXISTS memory_snapshots(id TEXT PRIMARY KEY, attempt_id TEXT UNIQUE NOT NULL,
 entries TEXT NOT NULL, hash TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS effect_ledger(effect_key TEXT PRIMARY KEY, attempt_id TEXT NOT NULL,
 delegation_id TEXT NOT NULL, owner_epoch INTEGER NOT NULL, target TEXT NOT NULL, idempotency_key TEXT NOT NULL,
 status TEXT NOT NULL, detail TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS dead_letters(id TEXT PRIMARY KEY, kind TEXT NOT NULL, ref TEXT NOT NULL,
 reason TEXT NOT NULL, detail TEXT, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS chat_resolvers(chat_id TEXT PRIMARY KEY, settings TEXT NOT NULL, source TEXT NOT NULL,
 updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS resolver_handoffs(id TEXT PRIMARY KEY, delegation_id TEXT NOT NULL,
 from_attempt_id TEXT NOT NULL, to_attempt_id TEXT NOT NULL, reason TEXT NOT NULL, actor TEXT NOT NULL,
 source TEXT NOT NULL, settings TEXT NOT NULL, bundle TEXT NOT NULL, bundle_hash TEXT NOT NULL,
 created_at REAL NOT NULL);
'''
TIERS = ('expert', 'resolver')
MEMORY_KINDS = ('working', 'episodic', 'semantic', 'procedural')
SKILL_LAYERS = ('platform', 'domain', 'performer')
SANDBOX_ORDER = ('read-only', 'workspace-write', 'danger-full-access')
LIVE_ATTEMPT = ('starting', 'running')
# Reversible settings for policies the Human has not decided. Each default keeps existing behavior and enables
# nothing destructive; `choices` lists every value the runtime implements.
POLICY = {
    'requireEmployment': {'default': False, 'choices': (False, True)},
    'replacement': {'default': 'keep-running', 'choices': ('keep-running', 'cancel-in-flight')},
    'skillRevocation': {'default': 'block-new-attempts', 'choices': ('block-new-attempts', 'cancel-active')},
    'memorySharing': {'default': 'domain-isolated', 'choices': ('domain-isolated', 'shared-semantic')},
    'memoryRetention': {'default': 'keep', 'choices': ('keep', 'expire-working')},
    'resolverAuto': {'default': 'off', 'choices': ('off', 'after-retries-exhausted', 'conductor-may-engage')},
}
NUMERIC = {'leaseSeconds': 900, 'retryBackoffSeconds': 0, 'retryBackoffMaxSeconds': 300}
# Decisions with no runtime switch: only the safe behavior exists until the Human decides otherwise.
FIXED = {'skillPublication': 'human-approval-only', 'externalCompensation': 'not-automatic',
         'unknownEffectOutcome': 'report-never-rerun', 'memoryDeletion': 'not-automatic',
         'resolverModel': 'explicit-selection-only'}


def _digest(value):
    from conductor.queue import digest
    return digest(value)


def _ident(prefix):
    from conductor.queue import ident
    return ident(prefix)


def _text(value, code, message, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ContractError(code, message)
    return value


def _source(value):
    return _text(value, 'source_required', 'Record the evidence for this change (a control command, run or decision)', 500)


def terms(text):
    return sorted({t for t in re.findall(r'\w+', text.casefold()) if len(t) >= 2})


class Performers:
    def __init__(self, store):
        self.store = store

    # -- reversible policy ---------------------------------------------------------------
    def settings(self, c):
        row = c.execute("SELECT value FROM meta WHERE key='performerPolicy'").fetchone()
        stored = json.loads(row[0]) if row else {}
        value = {k: stored.get(k, spec['default']) for k, spec in POLICY.items()}
        value.update({k: stored.get(k, default) for k, default in NUMERIC.items()})
        return value

    def configure(self, c, value, actor, source):
        if actor != 'human':
            raise ContractError('policy_protected', 'Only the Human changes undecided product policy')
        _source(source)
        if not isinstance(value, dict) or not value or set(value) - set(POLICY) - set(NUMERIC):
            raise ContractError('policy_invalid', 'Unknown performer policy setting')
        for key, item in value.items():
            if key in POLICY and item not in POLICY[key]['choices']:
                raise ContractError('policy_invalid', 'Unsupported value for ' + key)
            if key in NUMERIC and (type(item) not in (int, float) or not math.isfinite(item) or item < 0
                                   or (key == 'leaseSeconds' and item <= 0)):
                raise ContractError('policy_invalid', key + ' is a finite nonnegative number of seconds')
        row = c.execute("SELECT value FROM meta WHERE key='performerPolicy'").fetchone()
        stored = {**(json.loads(row[0]) if row else {}), **value}
        c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('performerPolicy', ?)", (json.dumps(stored),))
        self.store.op(c, 'performer-policy', keys=sorted(value), source=source)
        return self.settings(c)

    # -- domains, performers and employment ------------------------------------------------
    def domains(self):
        return [d for d in self.store.pool.catalog()['domains'] if not d.get('provisional')]

    def domain(self, domain_id):
        found = next((d for d in self.domains() if d['id'] == domain_id), None)
        if not found:
            raise ContractError('domain_missing', 'Select an existing named domain')
        return found

    def domain_of(self, c, delegation_id):
        area = self.store.pool.get_area(c, 'delegation', delegation_id)
        return area['domainId'] if area else None

    def active(self, c, domain_id):
        if not domain_id:
            return None
        row = c.execute("SELECT e.*, p.name AS performer_name FROM employments e JOIN performers p ON p.id=e.performer_id"
                        " WHERE e.domain_id=? AND e.status='active'", (domain_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _authority(value):
        value = value or {}
        if not isinstance(value, dict) or set(value) - {'sandboxCeiling', 'writeScopeCeiling'}:
            raise ContractError('employment_invalid', 'Employment authority holds a sandbox ceiling and write-scope ceiling only')
        if value.get('sandboxCeiling') is not None and value['sandboxCeiling'] not in SANDBOX_ORDER:
            raise ContractError('employment_invalid', 'Unknown sandbox ceiling')
        ceiling = value.get('writeScopeCeiling')
        if ceiling is not None and (not isinstance(ceiling, list) or not all(isinstance(p, str) and p for p in ceiling)):
            raise ContractError('employment_invalid', 'Write-scope ceiling is a list of project paths')
        return {'sandboxCeiling': value.get('sandboxCeiling'), 'writeScopeCeiling': ceiling}

    @staticmethod
    def _skill_scope(value):
        value = value or {}
        if not isinstance(value, dict) or set(value) - {'skills'} or not all(isinstance(s, str) for s in value.get('skills', [])):
            raise ContractError('employment_invalid', 'Skill scope lists skill IDs; omit it to use every approved skill of the domain')
        return {'skills': sorted(set(value['skills']))} if 'skills' in value else {}

    def _employ(self, c, performer_id, domain_id, revision, authority, skill_scope, actor, source, supersedes=None):
        eid = _ident('employment')
        c.execute('INSERT INTO employments(id, performer_id, domain_id, revision, status, authority, skill_scope,'
                  ' decision_ref, actor, supersedes, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                  (eid, performer_id, domain_id, revision, 'active', json.dumps(authority), json.dumps(skill_scope),
                   source, actor, supersedes, self.store.clock()))
        return eid

    def hire(self, c, domain_id, actor, source, *, name=None, authority=None, skill_scope=None):
        """Employment is an agreement with the Human: Main and the conductor can propose, never hire."""
        if actor != 'human':
            raise ContractError('employment_requires_human', 'Hiring a domain performer needs the Human agreement')
        _source(source)
        domain = self.domain(domain_id)
        current = self.active(c, domain_id)
        if current:
            return {'performerId': current['performer_id'], 'employmentId': current['id'], 'reused': True}
        pid = _ident('performer')
        c.execute('INSERT INTO performers VALUES(?,?,?,?,?)', (pid, domain_id, name or domain['name'], self.store.clock(), source))
        eid = self._employ(c, pid, domain_id, 1, self._authority(authority), self._skill_scope(skill_scope), actor, source)
        self.store.op(c, 'performer-hired', domainId=domain_id, performerId=pid, employmentId=eid)
        return {'performerId': pid, 'employmentId': eid, 'reused': False}

    def reconfigure(self, c, domain_id, actor, source, *, authority=None, skill_scope=None):
        if actor != 'human':
            raise ContractError('employment_requires_human', 'Employment terms change only with the Human agreement')
        current = self.active(c, domain_id)
        if not current:
            raise ContractError('employment_missing', 'This domain has no active employment')
        _source(source)
        authority = self._authority(authority if authority is not None else json.loads(current['authority']))
        scope = self._skill_scope(skill_scope if skill_scope is not None else json.loads(current['skill_scope']))
        self._end(c, current['id'], 'reconfigured', source)
        eid = self._employ(c, current['performer_id'], domain_id, current['revision'] + 1, authority, scope, actor, source, current['id'])
        return {'performerId': current['performer_id'], 'employmentId': eid, 'revision': current['revision'] + 1}

    def _end(self, c, employment_id, status, source):
        c.execute('UPDATE employments SET status=?, ended_at=?, end_reason=? WHERE id=?',
                  (status, self.store.clock(), source, employment_id))

    def replace(self, c, domain_id, actor, source, *, name=None, authority=None, skill_scope=None):
        """A new logical performer takes the domain; the former one and its sessions stay in history."""
        if actor != 'human':
            raise ContractError('employment_requires_human', 'Replacing a performer needs the Human agreement')
        current = self.active(c, domain_id)
        if not current:
            raise ContractError('employment_missing', 'This domain has no active employment to replace')
        _source(source)
        self._end(c, current['id'], 'replaced', source)
        hired = self.hire(c, domain_id, actor, source, name=name,
                          authority=authority if authority is not None else json.loads(current['authority']),
                          skill_scope=skill_scope if skill_scope is not None else json.loads(current['skill_scope']))
        c.execute('UPDATE employments SET supersedes=? WHERE id=?', (current['id'], hired['employmentId']))
        cancelled = self._in_flight(c, current['id'], source) if self.settings(c)['replacement'] == 'cancel-in-flight' else []
        return {**hired, 'replacedEmploymentId': current['id'], 'cancelledDelegations': cancelled}

    def retire(self, c, domain_id, actor, source):
        if actor != 'human':
            raise ContractError('employment_requires_human', 'Retiring a performer needs the Human agreement')
        current = self.active(c, domain_id)
        if not current:
            raise ContractError('employment_missing', 'This domain has no active employment')
        _source(source)
        self._end(c, current['id'], 'retired', source)
        cancelled = self._in_flight(c, current['id'], source) if self.settings(c)['replacement'] == 'cancel-in-flight' else []
        return {'retiredEmploymentId': current['id'], 'cancelledDelegations': cancelled}

    def _in_flight(self, c, employment_id, source):
        from conductor.queue import DELEGATION_TERMINAL
        done = []
        for row in list(c.execute('SELECT d.* FROM delegations d JOIN attempt_bindings b ON b.attempt_id=d.attempt_id'
                                  ' WHERE b.employment_id=? AND d.status NOT IN (?,?,?)', (employment_id, *DELEGATION_TERMINAL))):
            self.store.cancel_delegation(c, dict(row), 'policy:' + source)
            done.append(row['id'])
        return done

    # -- task ownership and serialized assignment --------------------------------------------
    def register_task(self, c, delegation, token, assignment_key=None):
        """Assignment commits are serialized by the queue transaction and logged with the deciding session."""
        from conductor.queue import DELEGATION_TERMINAL
        if assignment_key is not None:
            _text(assignment_key, 'assignment_invalid', 'assignmentKey is a nonempty string', 200)
            clash = c.execute('SELECT a.delegation_id FROM assignment_log a JOIN delegations d ON d.id=a.delegation_id'
                              ' WHERE a.request_id=? AND a.assignment_key=? AND d.status NOT IN (?,?,?)',
                              (delegation['request_id'], assignment_key, *DELEGATION_TERMINAL)).fetchone()
            if clash:
                raise ContractError('assignment_conflict', 'This assignment is already owned by open delegation ' + clash[0])
        c.execute('INSERT OR IGNORE INTO task_owners VALUES(?,?,?,?,?)',
                  (delegation['id'], 1, 1, _digest(json.loads(delegation['spec'])), None))
        c.execute('INSERT INTO assignment_log(delegation_id, request_id, assignment_key, domain_id, conductor_id, slot,'
                  ' epoch, turn_id, created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                  (delegation['id'], delegation['request_id'], assignment_key, self.domain_of(c, delegation['id']),
                   delegation['conductor_id'], token.get('slot'), token.get('epoch'), token.get('turnId'), self.store.clock()))
        return c.execute('SELECT seq FROM assignment_log WHERE delegation_id=?', (delegation['id'],)).fetchone()[0]

    def owner(self, c, delegation):
        row = self.store.row(c, 'SELECT * FROM task_owners WHERE delegation_id=?', delegation['id'])
        if row:
            return row
        # Delegations recorded before ownership existed start at revision 1, epoch 1; nothing is rewritten.
        c.execute('INSERT INTO task_owners VALUES(?,?,?,?,?)', (delegation['id'], 1, 1, _digest(json.loads(delegation['spec'])), None))
        return self.store.row(c, 'SELECT * FROM task_owners WHERE delegation_id=?', delegation['id'])

    def owner_view(self, c, delegation_id):
        """Read-only owner lookup for projections; legacy delegations read as revision 1, epoch 1."""
        return self.store.row(c, 'SELECT * FROM task_owners WHERE delegation_id=?', delegation_id) or {
            'task_revision': 1, 'owner_epoch': 1, 'result_attempt_id': None}

    def advance_epoch(self, c, delegation):
        owner = self.owner(c, delegation)
        c.execute('UPDATE task_owners SET owner_epoch=owner_epoch+1 WHERE delegation_id=?', (delegation['id'],))
        return owner['owner_epoch'] + 1

    def binding(self, c, attempt_id):
        return self.store.row(c, 'SELECT * FROM attempt_bindings WHERE attempt_id=?', attempt_id)

    def bind(self, c, delegation, attempt_id, *, tier='expert', not_before=None, handoff_id=None):
        """Bind a new attempt to the task owner epoch, logical performer and employment before it can start."""
        existing = self.binding(c, attempt_id)
        if existing:
            return existing
        owner = self.owner(c, delegation)
        employment = self.active(c, self.domain_of(c, delegation['id']))
        c.execute('INSERT INTO attempt_bindings(attempt_id, delegation_id, task_revision, owner_epoch, tier, performer_id,'
                  ' employment_id, not_before, handoff_id, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (attempt_id, delegation['id'], owner['task_revision'], owner['owner_epoch'], tier,
                   employment['performer_id'] if employment else None, employment['id'] if employment else None,
                   not_before, handoff_id, self.store.clock()))
        return self.binding(c, attempt_id)

    def retry_attempt(self, c, delegation, attempt_number):
        """A retry is a new attempt under a new owner epoch, after the configured backoff."""
        settings = self.settings(c)
        base = settings['retryBackoffSeconds']
        delay = min(base * 2 ** max(0, attempt_number - 2), settings['retryBackoffMaxSeconds']) if base else 0
        self.advance_epoch(c, delegation)
        return self.store.clock() + delay if delay else None

    def admission(self, c, delegation):
        """Ledger reasons an attempt may not start yet; None admits it."""
        binding = self.binding(c, delegation['attempt_id'])
        if binding and binding['not_before'] and self.store.clock() < binding['not_before']:
            return 'backoff'
        domain_id = self.domain_of(c, delegation['id'])
        employment = self.active(c, domain_id)
        if domain_id and not employment and self.settings(c)['requireEmployment']:
            return 'employment-required'
        if employment:
            authority = json.loads(employment['authority'])
            spec = json.loads(delegation['spec'])
            sandbox = spec.get('executionSettings', {}).get('sandbox') or self.store.policy(c, delegation['chat_id']).get('sandbox')
            if ((spec.get('workspace') or {}).get('mode') != 'read-only' and authority.get('sandboxCeiling') and sandbox
                    and SANDBOX_ORDER.index(sandbox) > SANDBOX_ORDER.index(authority['sandboxCeiling'])):
                return 'employment-authority:sandbox'
            ceiling = authority.get('writeScopeCeiling')
            if ceiling is not None and any(not any(_within(path, root) for root in ceiling) for path in spec.get('writeScope') or []):
                return 'employment-authority:write-scope'
        if binding and binding['tier'] == 'resolver' and not self.resolver_settings(c, delegation, binding=binding):
            return 'resolver-selection-required'
        return None

    def claim(self, c, delegation, attempt, worker_id):
        """Atomic start contract: session, pinned skill manifest, memory snapshot, claim token and lease."""
        binding = self.bind(c, delegation, attempt['id'])
        if binding['claim_token']:
            return binding
        now = self.store.clock()
        domain_id = self.domain_of(c, delegation['id'])
        employment = self.active(c, domain_id)
        # The performer is resolved when the attempt starts: a replacement before start takes over new work.
        c.execute('UPDATE attempt_bindings SET performer_id=?, employment_id=? WHERE attempt_id=?',
                  (employment['performer_id'] if employment else None, employment['id'] if employment else None, attempt['id']))
        binding = self.binding(c, attempt['id'])
        owner_id = binding['performer_id'] or ('unhired:' + domain_id if domain_id else 'unbound')
        if binding['tier'] == 'resolver':
            handoff = self.store.row(c, 'SELECT * FROM resolver_handoffs WHERE id=?', binding['handoff_id'])
            session_id = 'resolve-cq-' + attempt['id'][4:]
            settings = json.loads(handoff['settings']) if handoff else None
        else:
            session_id = worker_id or 'inline-' + attempt['id'][4:]
            settings = json.loads(delegation['spec']).get('executionSettings')
        old = self.store.row(c, 'SELECT * FROM exec_sessions WHERE id=?', session_id)
        if old:
            c.execute("UPDATE exec_sessions SET owner_kind='performer', owner_id=?, domain_id=?, state='active',"
                      " current_attempt_id=?, updated_at=? WHERE id=?", (owner_id, domain_id, attempt['id'], now, session_id))
        else:
            c.execute('INSERT INTO exec_sessions VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (session_id, 'performer', owner_id, domain_id, binding['tier'], json.dumps(settings), 'active',
                       attempt['id'], now, now))
        manifest = self.manifest(c, attempt['id'], delegation, binding)
        snapshot = self.snapshot(c, attempt['id'], {'kind': 'session', 'sessionId': session_id,
                                                    'performerId': binding['performer_id'], 'domainId': domain_id})
        token = _ident('claim')
        c.execute('UPDATE attempt_bindings SET session_id=?, manifest_id=?, snapshot_id=?, claim_token=?, lease_until=?,'
                  ' heartbeat_at=? WHERE attempt_id=?', (session_id, manifest['id'], snapshot['id'], token,
                                                       now + self.settings(c)['leaseSeconds'], now, attempt['id']))
        return self.binding(c, attempt['id'])

    def touch(self, c, attempt_id):
        """Any recorded worker event of the live attempt renews its lease."""
        c.execute('UPDATE attempt_bindings SET heartbeat_at=?, lease_until=? WHERE attempt_id=? AND claim_token IS NOT NULL',
                  (self.store.clock(), self.store.clock() + self.settings(c)['leaseSeconds'], attempt_id))

    def heartbeat(self, attempt_id, claim_token=None):
        with self.store.tx() as c:
            binding = self.binding(c, attempt_id)
            attempt = self.store.row(c, 'SELECT status FROM attempts WHERE id=?', attempt_id)
            if not binding or not attempt or attempt['status'] not in LIVE_ATTEMPT:
                return False
            if claim_token is not None and claim_token != binding['claim_token']:
                return False
            self.touch(c, attempt_id)
            return True

    def fence_event(self, c, delegation, attempt, payload):
        """A result is accepted only from the current attempt's live claim and owner epoch."""
        binding = self.binding(c, attempt['id'])
        if not binding:
            return None
        if attempt['status'] == 'lost':
            return 'lease-lost'
        if payload.get('ownerEpoch') is not None and payload['ownerEpoch'] != self.owner_view(c, delegation['id'])['owner_epoch']:
            return 'stale-epoch'
        if payload.get('claimToken') is not None and payload['claimToken'] != binding['claim_token']:
            return 'stale-claim'
        return None

    def settle(self, c, delegation, attempt, kind):
        """Terminal attempt: release its session, record the single result owner, emit memory intents."""
        now = self.store.clock()
        binding = self.binding(c, attempt['id'])
        if binding and binding['session_id']:
            state = 'retired' if binding['tier'] == 'resolver' else 'idle'
            c.execute('UPDATE exec_sessions SET state=?, current_attempt_id=NULL, updated_at=? WHERE id=? AND current_attempt_id=?',
                      (state, now, binding['session_id'], attempt['id']))
            if self.settings(c)['memoryRetention'] == 'expire-working':
                c.execute("UPDATE memory_entries SET status='expired' WHERE kind='working' AND scope_id=? AND status='active'",
                          (binding['session_id'],))
        if kind == 'completed':
            c.execute('UPDATE task_owners SET result_attempt_id=? WHERE delegation_id=? AND result_attempt_id IS NULL',
                      (attempt['id'], delegation['id']))
        if kind in ('completed', 'failed'):
            current = self.store.row(c, 'SELECT * FROM delegations WHERE id=?', delegation['id'])
            outcome = json.loads((current['result'] if kind == 'completed' else current['error']) or 'null')
            summary = outcome.get('summary') or outcome.get('message') if isinstance(outcome, dict) else None
            text = '%s: %s — %s' % ('Completed' if kind == 'completed' else 'Failed', current['title'],
                                     summary or json.dumps(outcome, ensure_ascii=False, sort_keys=True))
            self.memory_intent(c, current['chat_id'], {
                'kind': 'episodic', 'scopeKind': 'task', 'scopeId': delegation['id'],
                'domainId': self.domain_of(c, delegation['id']), 'text': text[:4000],
                'sourceRef': 'attempt:' + attempt['id'], 'writer': 'runtime', 'confidence': None,
                'retention': 'keep'}, key='episodic:%s:%s' % (attempt['id'], kind))

    def expire_leases(self):
        """Lease expiry fences the silent attempt; its later result is recorded as late and changes nothing."""
        from conductor.queue import ident
        handled = 0
        with self.store.tx() as c:
            now = self.store.clock()
            rows = [dict(r) for r in c.execute(
                'SELECT a.*, b.lease_until FROM attempts a JOIN attempt_bindings b ON b.attempt_id=a.id JOIN delegations d'
                " ON d.attempt_id=a.id WHERE a.status IN ('starting','running') AND d.status NOT IN ('awaiting-answer')"
                ' AND b.lease_until IS NOT NULL AND b.lease_until < ?', (now,))]
            for attempt in rows:
                d = self.store.row(c, 'SELECT * FROM delegations WHERE id=?', attempt['delegation_id'])
                c.execute("UPDATE attempts SET status='lost', ended_at=?, updated_at=? WHERE id=?", (now, now, attempt['id']))
                self.store.pool.release_worker(c, attempt['id'])
                self.settle(c, d, attempt, 'lost')
                error = {'code': 'lease-expired', 'retryable': True, 'message': 'No heartbeat before the lease expired'}
                self.store.event(c, d['chat_id'], 'attempt-lease-expired', {'delegation': self.store.public_delegation(c, d),
                                                                           'attemptId': attempt['id']})
                self.store.op(c, 'lease-expired', delegationId=d['id'], attemptId=attempt['id'])
                if d['cancel_requested']:
                    d = self.store.set_delegation(c, d, 'cancelled')
                    self.store.event(c, d['chat_id'], 'delegation-cancelled', {'delegation': self.store.public_delegation(c, d)})
                elif d['attempt_count'] < d['max_attempts']:
                    aid = ident('att')
                    c.execute('INSERT INTO attempts(id, delegation_id, number, status, backend, created_at, updated_at)'
                              ' VALUES(?,?,?,?,?,?,?)', (aid, d['id'], d['attempt_count'] + 1, 'pending', attempt['backend'], now, now))
                    not_before = self.retry_attempt(c, d, d['attempt_count'] + 1)
                    previous = self.binding(c, attempt['id'])
                    self.bind(c, d, aid, tier=previous['tier'] if previous else 'expert', not_before=not_before,
                              handoff_id=previous['handoff_id'] if previous else None)
                    d = self.store.set_delegation(c, d, 'dispatched', attempt_id=aid, attempt_count=d['attempt_count'] + 1,
                                                  error=json.dumps(error))
                    self.store.event(c, d['chat_id'], 'attempt-retry', {'delegation': self.store.public_delegation(c, d),
                                                                       'previousAttemptId': attempt['id'], 'error': error})
                elif not self.exhausted(c, d, attempt, error):
                    d = self.store.set_delegation(c, d, 'failed', error=json.dumps(error))
                    self.store.event(c, d['chat_id'], 'delegation-failed', {'delegation': self.store.public_delegation(c, d)})
                    self.dead_letter(c, 'attempt', attempt['id'], 'lease-expired', {'delegationId': d['id']})
                    self.settle(c, d, attempt, 'failed')
                self.store.close_questions(c, d['request_id'], 'closed-lost', delegation_id=d['id'])
                self.store.settle_request(c, d['request_id'])
                handled += 1
        return handled

    def exhausted(self, c, delegation, attempt, error):
        """Retries are spent: escalate to the resolver only when the Human enabled it and selected its settings."""
        if self.settings(c)['resolverAuto'] == 'off' or delegation['cancel_requested']:
            return False
        if c.execute('SELECT 1 FROM resolver_handoffs WHERE delegation_id=?', (delegation['id'],)).fetchone():
            return False
        if not self.resolver_settings(c, delegation):
            return False
        self.escalate(c, delegation, 'retries-exhausted:' + str((error or {}).get('code')), 'policy',
                      'performer-policy:resolverAuto', failed_attempt=attempt)
        return True

    # -- dead letters ------------------------------------------------------------------------
    def dead_letter(self, c, kind, ref, reason, detail=None):
        c.execute('INSERT OR IGNORE INTO dead_letters VALUES(?,?,?,?,?,?)',
                  ('dlq-' + _digest([kind, ref])[:24], kind, ref, reason, json.dumps(detail or {}), self.store.clock()))

    def dead_letters(self, c):
        return [{**dict(r), 'detail': json.loads(r['detail'] or '{}')} for r in c.execute('SELECT * FROM dead_letters ORDER BY created_at')]

    # -- skills --------------------------------------------------------------------------------
    def register_skill(self, c, skill_id, layer, scope_id, source_ref, content_hash, actor, source, *, origin=None):
        """Register a skill revision as a candidate; only the Human approves it for execution."""
        _text(skill_id, 'skill_invalid', 'Skill ID required', 200)
        _text(source_ref, 'skill_invalid', 'Skill source path or URI required', 1000)
        if not isinstance(content_hash, str) or not re.fullmatch(r'[0-9a-f]{16,64}', content_hash):
            raise ContractError('skill_invalid', 'Skill content hash required')
        if layer not in SKILL_LAYERS or (layer == 'platform') != (scope_id is None):
            raise ContractError('skill_invalid', 'Platform skills have no scope; domain and performer skills name theirs')
        if actor not in ('human', 'ai', 'runtime'):
            raise ContractError('skill_invalid', 'Unknown actor')
        _source(source)
        same = self.store.row(c, 'SELECT * FROM skill_revisions WHERE skill_id=? AND content_hash=? AND layer=? AND scope_id IS ?',
                              skill_id, content_hash, layer, scope_id)
        if same:
            return {'skillRevisionId': same['id'], 'revision': same['revision'], 'status': same['status'], 'reused': True}
        revision = (c.execute('SELECT MAX(revision) FROM skill_revisions WHERE skill_id=?', (skill_id,)).fetchone()[0] or 0) + 1
        rid = 'skillrev-' + _digest([skill_id, revision])[:20]
        now = self.store.clock()
        c.execute('INSERT INTO skill_revisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (rid, skill_id, revision, layer, scope_id, source_ref, content_hash, 'candidate', origin, actor, None, None, now, now))
        return {'skillRevisionId': rid, 'revision': revision, 'status': 'candidate', 'reused': False}

    def approve_skill(self, c, revision_id, actor, source):
        if actor != 'human':
            raise ContractError('skill_publication_requires_human', 'Skills are published only by the Human')
        row = self.store.row(c, 'SELECT * FROM skill_revisions WHERE id=?', revision_id)
        if not row or row['status'] != 'candidate':
            raise ContractError('skill_invalid', 'Approve an existing candidate revision')
        c.execute("UPDATE skill_revisions SET status='approved', approval_ref=?, updated_at=? WHERE id=?",
                  (_source(source), self.store.clock(), revision_id))
        return {'skillRevisionId': revision_id, 'status': 'approved'}

    def revoke_skill(self, c, revision_id, actor, source, reason):
        if actor != 'human':
            raise ContractError('skill_revocation_requires_human', 'Skills are revoked by the Human')
        row = self.store.row(c, 'SELECT * FROM skill_revisions WHERE id=?', revision_id)
        if not row or row['status'] == 'revoked':
            raise ContractError('skill_invalid', 'Revoke an existing active or candidate revision')
        _source(source)
        c.execute("UPDATE skill_revisions SET status='revoked', revoked_reason=?, updated_at=? WHERE id=?",
                  (_text(reason, 'skill_invalid', 'Revocation reason required', 500), self.store.clock(), revision_id))
        cancelled = []
        if self.settings(c)['skillRevocation'] == 'cancel-active':
            from conductor.queue import DELEGATION_TERMINAL
            for row in list(c.execute('SELECT d.*, m.skills FROM delegations d JOIN attempt_bindings b ON b.attempt_id=d.attempt_id'
                                      ' JOIN execution_manifests m ON m.id=b.manifest_id JOIN attempts a ON a.id=d.attempt_id'
                                      " WHERE a.status IN ('starting','running') AND d.status NOT IN (?,?,?)", DELEGATION_TERMINAL)):
                if any(s['revisionId'] == revision_id for s in json.loads(row['skills'])):
                    self.store.cancel_delegation(c, {k: row[k] for k in row.keys() if k != 'skills'}, 'skill-revoked:' + revision_id)
                    cancelled.append(row['id'])
        return {'skillRevisionId': revision_id, 'status': 'revoked', 'cancelledDelegations': cancelled}

    def manifest(self, c, attempt_id, delegation, binding):
        """Pin approved skill revisions for this attempt: platform, then domain, then this performer's own."""
        existing = self.store.row(c, 'SELECT * FROM execution_manifests WHERE attempt_id=?', attempt_id)
        if existing:
            return existing
        domain_id = self.domain_of(c, delegation['id'])
        employment = self.store.row(c, 'SELECT * FROM employments WHERE id=?', binding['employment_id']) if binding['employment_id'] else None
        allowed = set(json.loads(employment['skill_scope']).get('skills', [])) if employment and json.loads(employment['skill_scope']).get('skills') is not None else None
        chosen = {}
        for row in c.execute("SELECT * FROM skill_revisions WHERE status='approved' ORDER BY revision"):
            fits = (row['layer'] == 'platform' or (row['layer'] == 'domain' and row['scope_id'] == domain_id)
                    or (row['layer'] == 'performer' and binding['performer_id'] and row['scope_id'] == binding['performer_id']))
            if not fits or (allowed is not None and row['layer'] != 'platform' and row['skill_id'] not in allowed):
                continue
            chosen[(row['layer'], row['skill_id'])] = row  # The latest approved revision of each skill.
        skills = [{'revisionId': r['id'], 'skillId': r['skill_id'], 'revision': r['revision'], 'layer': r['layer'],
                   'scopeId': r['scope_id'], 'sourceRef': r['source_ref'], 'contentHash': r['content_hash']}
                  for r in sorted(chosen.values(), key=lambda r: (SKILL_LAYERS.index(r['layer']), r['skill_id']))]
        spec = json.loads(delegation['spec'])
        policy = self.store.policy(c, delegation['chat_id'])
        authority = {'writeScope': spec.get('writeScope', []), 'sandbox': policy.get('sandbox'),
                     'approvalPolicy': policy['approvalPolicy'], 'employmentId': binding['employment_id'],
                     # Precedence: platform safety > employment/task authority > domain > performer > memory.
                     'precedence': ['platform', 'authority', 'domain', 'performer', 'procedural-memory'],
                     'skillsGrantAuthority': False}
        mid = 'manifest-' + attempt_id[4:]
        c.execute('INSERT INTO execution_manifests VALUES(?,?,?,?,?,?)',
                  (mid, attempt_id, json.dumps(skills), json.dumps(authority), _digest([skills, authority])[:24], self.store.clock()))
        return self.store.row(c, 'SELECT * FROM execution_manifests WHERE id=?', mid)

    def propose_skill(self, c, entry_id, skill_id, actor, source):
        """Experience → procedural memory → skill candidate; publication stays a separate Human approval."""
        entry = self.store.row(c, 'SELECT * FROM memory_entries WHERE id=?', entry_id)
        if not entry or entry['kind'] != 'procedural' or entry['status'] not in ('active', 'candidate'):
            raise ContractError('skill_invalid', 'Only a recorded procedural memory entry becomes a skill candidate')
        layer, scope = ('performer', entry['scope_id']) if entry['scope_kind'] == 'performer' else ('domain', entry['domain_id'])
        return self.register_skill(c, skill_id, layer, scope, 'memory:' + entry_id, _digest(entry['text'])[:40], actor, source,
                                   origin='memory:' + entry_id)

    # -- memory ----------------------------------------------------------------------------------
    def _validate_entry(self, c, entry):
        if not isinstance(entry, dict) or entry.get('kind') not in MEMORY_KINDS:
            raise ContractError('memory_invalid', 'Memory kind is working, episodic, semantic or procedural')
        _text(entry.get('text'), 'memory_invalid', 'Memory text required')
        _text(entry.get('sourceRef'), 'memory_provenance_required', 'Every memory entry names its source record', 500)
        _text(entry.get('writer'), 'memory_invalid', 'Writer required', 200)
        scope = {'working': ('session',), 'episodic': ('task', 'request'), 'semantic': ('domain',),
                 'procedural': ('performer', 'domain')}[entry['kind']]
        if entry.get('scopeKind') not in scope or not isinstance(entry.get('scopeId'), str) or not entry['scopeId']:
            raise ContractError('memory_scope_invalid', '%s memory belongs to a %s' % (entry['kind'], ' or '.join(scope)))
        confidence = entry.get('confidence')
        if confidence is not None and (type(confidence) not in (int, float) or not 0 <= confidence <= 1):
            raise ContractError('memory_invalid', 'Confidence is a number from 0 to 1 or null')

    def _authorize_write(self, writer, entry):
        """Owner scopes: a session writes its working memory; shared kinds from non-Human writers are candidates."""
        kind = writer.get('kind')
        if entry['kind'] == 'working':
            if kind != 'session' or writer.get('sessionId') != entry['scopeId']:
                raise ContractError('memory_scope_denied', 'Working memory is written only by its own session')
            return 'active'
        if kind == 'human':
            return 'active'
        if kind in ('performer', 'session') and entry.get('domainId') != writer.get('domainId'):
            raise ContractError('memory_scope_denied', 'A performer writes only its own domain memory')
        if entry['kind'] == 'procedural' and entry['scopeKind'] == 'performer' and writer.get('performerId') != entry['scopeId'] and kind != 'runtime':
            raise ContractError('memory_scope_denied', 'Performer procedural memory belongs to that performer')
        if entry['kind'] == 'episodic':
            return 'active'
        return 'candidate'  # Semantic and procedural knowledge needs Human approval before it is shared as active.

    def write_memory(self, c, chat_id, entry, writer, *, key=None):
        """Memory changes are outbox intents; the memory subscription applies them idempotently after commit."""
        self._validate_entry(c, entry)
        status = self._authorize_write(writer, entry)
        return self.memory_intent(c, chat_id, {**entry, 'writer': entry['writer'], 'status': status}, key=key)

    def memory_intent(self, c, chat_id, entry, *, key=None):
        self._validate_entry(c, entry)
        entry = {'status': 'active', 'contradiction': 'none', 'retention': 'keep', 'supersedes': None,
                 'observedAt': self.store.clock(), **entry}
        entry['id'] = 'mem-' + _digest(['memory', key or [entry['sourceRef'], entry['kind'], entry['scopeId'], entry['text']]])[:24]
        self.store.event(c, chat_id, 'memory-update-intent', {'entry': entry}, key='memory:' + entry['id'])
        return entry['id']

    def memory_handler(self, c, event):
        if event['type'] != 'memory-update-intent':
            return None
        e = event['payload']['entry']
        cur = c.execute('INSERT OR IGNORE INTO memory_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (e['id'], e['kind'], e['scopeKind'], e['scopeId'], e.get('domainId'), e['text'], e['sourceRef'],
                         e['observedAt'], e['writer'], e.get('confidence'), e.get('supersedes'), e['contradiction'],
                         e['retention'], e['status'], self.store.clock()))
        if cur.rowcount:
            if e.get('supersedes'):
                c.execute("UPDATE memory_entries SET status='superseded' WHERE id=? AND status IN ('active','candidate','contested')",
                          (e['supersedes'],))
            for term in terms(e['text']):
                c.execute('INSERT OR IGNORE INTO memory_index VALUES(?,?)', (term, e['id']))
        return None

    def correct_memory(self, c, chat_id, entry_id, text, writer, source):
        """A correction is a new entry that supersedes the old one; the original text stays recorded."""
        old = self.store.row(c, 'SELECT * FROM memory_entries WHERE id=?', entry_id)
        if not old:
            raise ContractError('memory_missing', 'Correct an applied memory entry')
        entry = {'kind': old['kind'], 'scopeKind': old['scope_kind'], 'scopeId': old['scope_id'], 'domainId': old['domain_id'],
                 'text': text, 'sourceRef': _source(source), 'writer': writer.get('id') or writer['kind'],
                 'confidence': old['confidence'], 'retention': old['retention'], 'supersedes': entry_id}
        return self.write_memory(c, chat_id, entry, writer, key='correct:%s:%s' % (entry_id, _digest(text)))

    def contradict_memory(self, c, first_id, second_id, source):
        rows = [self.store.row(c, 'SELECT * FROM memory_entries WHERE id=?', i) for i in (first_id, second_id)]
        if not all(rows) or first_id == second_id:
            raise ContractError('memory_missing', 'Name two applied memory entries')
        _source(source)
        for row, other in ((rows[0], second_id), (rows[1], first_id)):
            c.execute("UPDATE memory_entries SET contradiction=? WHERE id=?", ('contested-with:' + other, row['id']))
        return {'contested': [first_id, second_id]}

    def approve_memory(self, c, entry_id, actor, source):
        if actor != 'human':
            raise ContractError('memory_approval_requires_human', 'Shared semantic and procedural memory is approved by the Human')
        _source(source)
        cur = c.execute("UPDATE memory_entries SET status='active' WHERE id=? AND status='candidate'", (entry_id,))
        if not cur.rowcount:
            raise ContractError('memory_invalid', 'Approve an applied candidate entry')
        return {'entryId': entry_id, 'status': 'active'}

    def readable(self, c, reader, row, settings=None):
        kind = reader.get('kind')
        if row['status'] in ('expired', 'rejected'):
            return False
        if kind == 'human':
            return True
        if row['kind'] == 'working':
            return kind == 'session' and reader.get('sessionId') == row['scope_id']
        if kind == 'conductor':
            return True
        if kind not in ('performer', 'session'):
            return False
        same = row['domain_id'] is not None and row['domain_id'] == reader.get('domainId')
        if row['kind'] == 'semantic' and not same:
            settings = settings or self.settings(c)
            return settings['memorySharing'] == 'shared-semantic' and row['status'] == 'active'
        if row['kind'] == 'procedural' and row['scope_kind'] == 'performer':
            return row['scope_id'] == reader.get('performerId')
        return same

    def search(self, reader, query, *, include_inactive=False):
        """Lexical index lookup filtered by the reader's ownership scope; results point back to sources."""
        wanted = terms(_text(query, 'memory_query', 'Query text required', 1000))
        c = self.store.connection()
        settings = self.settings(c)
        rows = [dict(r) for r in c.execute('SELECT * FROM memory_entries ORDER BY observed_at DESC, id')]
        if wanted:
            hits = None
            for term in wanted:
                ids = {r[0] for r in c.execute('SELECT entry_id FROM memory_index WHERE term=?', (term,))}
                hits = ids if hits is None else hits & ids
            rows = [r for r in rows if r['id'] in hits]
        return [self.public_memory(r) for r in rows if self.readable(c, reader, r, settings)
                and (include_inactive or r['status'] in ('active', 'candidate'))]

    def reindex(self):
        """The search index is a projection: rebuild it from the entries at any time."""
        with self.store.tx() as c:
            c.execute('DELETE FROM memory_index')
            count = 0
            for row in c.execute('SELECT id, text FROM memory_entries'):
                for term in terms(row['text']):
                    c.execute('INSERT OR IGNORE INTO memory_index VALUES(?,?)', (term, row['id']))
                count += 1
            self.store.op(c, 'memory-reindexed', entries=count)
        return count

    def snapshot(self, c, attempt_id, reader):
        existing = self.store.row(c, 'SELECT * FROM memory_snapshots WHERE attempt_id=?', attempt_id)
        if existing:
            return existing
        settings = self.settings(c)
        entries = [{'id': r['id'], 'kind': r['kind'], 'status': r['status'], 'hash': _digest(r['text'])[:16],
                    'sourceRef': r['source_ref']}
                   for r in c.execute("SELECT * FROM memory_entries WHERE status IN ('active','candidate') ORDER BY observed_at, id")
                   if self.readable(c, reader, r, settings)]
        sid = 'snapshot-' + attempt_id[4:]
        c.execute('INSERT INTO memory_snapshots VALUES(?,?,?,?,?)',
                  (sid, attempt_id, json.dumps(entries), _digest(entries)[:24], self.store.clock()))
        return self.store.row(c, 'SELECT * FROM memory_snapshots WHERE id=?', sid)

    def restore(self, c, snapshot_id):
        """Return a snapshot's entries as recorded, flagging later corrections instead of rewriting them."""
        row = self.store.row(c, 'SELECT * FROM memory_snapshots WHERE id=?', snapshot_id)
        if not row:
            raise ContractError('snapshot_missing', 'Unknown memory snapshot')
        restored = []
        for item in json.loads(row['entries']):
            entry = self.store.row(c, 'SELECT * FROM memory_entries WHERE id=?', item['id'])
            later = self.store.row(c, 'SELECT id FROM memory_entries WHERE supersedes=?', item['id'])
            restored.append({**item, 'text': entry['text'] if entry else None, 'currentStatus': entry['status'] if entry else 'missing',
                             'supersededBy': later['id'] if later else None,
                             'contradiction': entry['contradiction'] if entry else None})
        return {'snapshotId': snapshot_id, 'attemptId': row['attempt_id'], 'hash': row['hash'], 'entries': restored}

    @staticmethod
    def public_memory(r):
        return {'id': r['id'], 'kind': r['kind'], 'scopeKind': r['scope_kind'], 'scopeId': r['scope_id'],
                'domainId': r['domain_id'], 'text': r['text'], 'sourceRef': r['source_ref'], 'observedAt': r['observed_at'],
                'writer': r['writer'], 'confidence': r['confidence'], 'supersedes': r['supersedes'],
                'contradictionState': r['contradiction'], 'retentionClass': r['retention'], 'status': r['status']}

    # -- external effects ---------------------------------------------------------------------------
    def effect_intent(self, attempt_id, target, idempotency_key, *, claim_token=None):
        """Record the intent before the external call; a stable key survives retries and session changes."""
        _text(target, 'effect_invalid', 'Effect target required', 500)
        _text(idempotency_key, 'effect_invalid', 'Idempotency key required', 200)
        with self.store.tx() as c:
            attempt = self.store.row(c, 'SELECT * FROM attempts WHERE id=?', attempt_id)
            d = attempt and self.store.row(c, 'SELECT * FROM delegations WHERE id=?', attempt['delegation_id'])
            binding = self.binding(c, attempt_id)
            if (not d or not binding or d['attempt_id'] != attempt_id or attempt['status'] not in LIVE_ATTEMPT
                    or d['cancel_requested'] or (claim_token is not None and claim_token != binding['claim_token'])):
                raise ContractError('effect_fenced', 'Only the live current attempt starts new external effects')
            owner = self.owner(c, d)
            key = 'effect-' + _digest([d['id'], owner['task_revision'], target, idempotency_key])[:24]
            old = self.store.row(c, 'SELECT * FROM effect_ledger WHERE effect_key=?', key)
            if old:
                # Never repeat a succeeded effect, and never guess the outcome of an unknown one.
                return {'effectKey': key, 'status': old['status'], 'proceed': old['status'] == 'failed'}
            now = self.store.clock()
            c.execute('INSERT INTO effect_ledger VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (key, attempt_id, d['id'], owner['owner_epoch'], target, idempotency_key, 'intent', None, now, now))
            self.touch(c, attempt_id)
            return {'effectKey': key, 'status': 'intent', 'proceed': True}

    def effect_outcome(self, effect_key, status, detail=None):
        if status not in ('succeeded', 'failed', 'unknown'):
            raise ContractError('effect_invalid', 'Outcome is succeeded, failed or unknown')
        with self.store.tx() as c:
            row = self.store.row(c, 'SELECT * FROM effect_ledger WHERE effect_key=?', effect_key)
            if not row:
                raise ContractError('effect_missing', 'Unknown effect key')
            if row['status'] == 'succeeded' and status != 'succeeded':
                return {'effectKey': effect_key, 'status': 'succeeded'}  # A confirmed success is never relabelled.
            c.execute('UPDATE effect_ledger SET status=?, detail=?, updated_at=? WHERE effect_key=?',
                      ('outcome-unknown' if status == 'unknown' else status, json.dumps(detail) if detail else row['detail'],
                       self.store.clock(), effect_key))
            return {'effectKey': effect_key, 'status': 'outcome-unknown' if status == 'unknown' else status}

    def uncertain_effects(self, c):
        """After a crash, intents without an outcome become outcome-unknown and are reported, never re-run."""
        rows = [dict(r) for r in c.execute("SELECT * FROM effect_ledger WHERE status='intent'")]
        for row in rows:
            c.execute("UPDATE effect_ledger SET status='outcome-unknown', updated_at=? WHERE effect_key=?",
                      (self.store.clock(), row['effect_key']))
            d = self.store.row(c, 'SELECT chat_id FROM delegations WHERE id=?', row['delegation_id'])
            self.store.event(c, d['chat_id'] if d else None, 'effect-outcome-unknown',
                             {'effectKey': row['effect_key'], 'attemptId': row['attempt_id'], 'delegationId': row['delegation_id'],
                              'target': row['target']}, key='effect-unknown:' + row['effect_key'])
        unknown = [r[0] for r in c.execute("SELECT effect_key FROM effect_ledger WHERE status='outcome-unknown'")]
        return unknown

    # -- resolver ------------------------------------------------------------------------------------
    def configure_chat_resolver(self, c, chat_id, settings, source):
        """The chat's own Resolver selection (its settings row). Same validation as an area setting; never widens authority."""
        _source(source)
        if (not isinstance(settings, dict) or not settings.get('model') or settings.get('provider') not in ('codex', 'claude', 'antigravity')
                or set(settings) - {'model', 'provider', 'reasoningEffort', 'fast', 'sandbox', 'approvalPolicy'}):
            raise ContractError('role_setting_invalid', 'Use an explicit Resolver model/provider setting')
        policy = self.store.policy(c, chat_id)
        if settings.get('sandbox') != policy.get('sandbox') or settings.get('approvalPolicy') != policy['approvalPolicy']:
            raise ContractError('role_permission_invalid', 'Resolver permissions must match the captured chat authority')
        old = self.store.row(c, 'SELECT settings FROM chat_resolvers WHERE chat_id=?', chat_id)
        if old and json.loads(old['settings']) == settings:
            return {'configured': True, 'changed': False}
        c.execute('INSERT OR REPLACE INTO chat_resolvers VALUES(?,?,?,?)', (chat_id, json.dumps(settings, sort_keys=True), source, self.store.clock()))
        return {'configured': True, 'changed': True}

    def resolver_settings(self, c, delegation, *, binding=None):
        """Explicitly selected resolver settings only: the delegation's domain/child setting, then the chat policy."""
        if binding and binding['handoff_id']:
            handoff = self.store.row(c, 'SELECT settings FROM resolver_handoffs WHERE id=?', binding['handoff_id'])
            if handoff:
                return json.loads(handoff['settings'])
        area = self.store.pool.get_area(c, 'delegation', delegation['id']) or {}
        policy = self.store.policy(c, delegation['chat_id'])
        chat = self.store.row(c, 'SELECT settings FROM chat_resolvers WHERE chat_id=?', delegation['chat_id'])
        for aid in (area.get('subdomainId'), area.get('domainId')):
            row = c.execute("SELECT settings FROM area_role_settings WHERE area_id=? AND role='resolver'", (aid,)).fetchone() if aid else None
            if row:
                settings = json.loads(row[0])
                break
        else:
            raw = json.loads(chat['settings']) if chat else (policy.get('roleSettings') or {}).get('resolver')
            if not raw or not raw.get('model') or not raw.get('provider'):
                return None
            settings = {**raw, 'sandbox': raw.get('sandbox', policy.get('sandbox')),
                        'approvalPolicy': raw.get('approvalPolicy', policy['approvalPolicy'])}
        if settings.get('sandbox') != policy.get('sandbox') or settings.get('approvalPolicy') != policy['approvalPolicy']:
            return None  # A resolver never widens or changes the captured task authority.
        return settings

    def resolver_state(self, c, area, policy, chat_id=None):
        for aid in (area.get('subdomainId'), area.get('domainId')):
            row = c.execute("SELECT settings, source FROM area_role_settings WHERE area_id=? AND role='resolver'", (aid,)).fetchone() if aid else None
            if row:
                return {'state': 'configured', 'settings': json.loads(row[0]), 'source': row[1], 'inheritedFrom': aid}
        chat = self.store.row(c, 'SELECT settings, source FROM chat_resolvers WHERE chat_id=?', chat_id) if chat_id else None
        if chat:
            return {'state': 'configured', 'settings': json.loads(chat['settings']), 'source': chat['source'], 'inheritedFrom': 'chat'}
        raw = ((policy or {}).get('roleSettings') or {}).get('resolver')
        if raw and raw.get('model'):
            return {'state': 'configured', 'settings': raw, 'source': 'chat-policy', 'inheritedFrom': None}
        return {'state': 'selection-required', 'settings': None, 'source': None, 'inheritedFrom': None}

    def escalate(self, c, delegation, reason, actor, source, *, failed_attempt=None):
        """Hand the same task to a resolver session of the same logical performer, keeping scope and authority."""
        from conductor.queue import ident
        _text(reason, 'resolver_reason_required', 'Record why the resolver is engaged', 1000)
        _source(source)
        if actor not in ('human', 'conductor', 'policy'):
            raise ContractError('resolver_actor_invalid', 'Resolver engagement is by the Human, conductor or enabled policy')
        d = self.store.row(c, 'SELECT * FROM delegations WHERE id=?', delegation['id'])
        req = self.store.row(c, 'SELECT * FROM requests WHERE id=?', d['request_id'])
        if req['status'] in ('completed', 'cancelled', 'cancelling') or d['cancel_requested']:
            raise ContractError('resolver_target_closed', 'The request or task is closed or being cancelled')
        attempt = failed_attempt or self.store.row(c, 'SELECT * FROM attempts WHERE id=?', d['attempt_id'])
        escalatable = d['status'] in ('failed', 'awaiting-answer') or attempt['status'] in ('pending', 'failed', 'lost')
        if not escalatable:
            raise ContractError('resolver_attempt_active', 'Wait for or cancel the running attempt before engaging the resolver')
        settings = self.resolver_settings(c, d)
        if not settings:
            raise ContractError('resolver_selection_required', 'Select the resolver provider, model and effort explicitly first')
        now = self.store.clock()
        epoch = self.advance_epoch(c, d)
        aid = ident('att')
        previous = []
        for row in c.execute('SELECT * FROM attempts WHERE delegation_id=? ORDER BY number', (d['id'],)):
            binding = self.binding(c, row['id'])
            previous.append({'attemptId': row['id'], 'number': row['number'], 'status': row['status'],
                             'error': json.loads(row['error'] or 'null'), 'progress': json.loads(row['progress'] or 'null'),
                             'external': json.loads(row['external'] or 'null'),
                             'tier': binding['tier'] if binding else 'expert',
                             'manifestId': binding['manifest_id'] if binding else None,
                             'snapshotId': binding['snapshot_id'] if binding else None})
        spec = json.loads(d['spec'])
        last = self.binding(c, attempt['id'])
        bundle = {'delegationId': d['id'], 'requestId': d['request_id'], 'title': d['title'],
                  'taskRevision': self.owner(c, d)['task_revision'], 'ownerEpoch': epoch,
                  'scope': {'goal': spec.get('goal') or d['title'], 'completionCriteria': spec.get('completionCriteria'),
                            'writeScope': spec.get('writeScope', []), 'workProfile': spec.get('workProfile')},
                  'authority': {'sandbox': self.store.policy(c, d['chat_id']).get('sandbox'),
                                'approvalPolicy': self.store.policy(c, d['chat_id'])['approvalPolicy'], 'unchanged': True},
                  'previousAttempts': previous, 'failureEvidence': json.loads(d['error'] or 'null'),
                  'pinnedManifestId': last['manifest_id'] if last else None,
                  'memorySnapshotId': last['snapshot_id'] if last else None,
                  'openQuestions': [self.store.question_view(dict(q)) for q in c.execute(
                      "SELECT * FROM questions WHERE delegation_id=? AND state='pending'", (d['id'],))],
                  'uncertainEffects': [dict(r) for r in c.execute(
                      "SELECT effect_key, target, status FROM effect_ledger WHERE delegation_id=? AND status IN ('intent','outcome-unknown')", (d['id'],))],
                  'reason': reason, 'engagedBy': actor, 'source': source}
        hid = 'resolver-' + aid[4:]
        c.execute('INSERT INTO resolver_handoffs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                  (hid, d['id'], attempt['id'], aid, reason, actor, source, json.dumps(settings), json.dumps(bundle, ensure_ascii=False),
                   _digest(bundle)[:24], now))
        c.execute('INSERT INTO attempts(id, delegation_id, number, status, backend, created_at, updated_at) VALUES(?,?,?,?,?,?,?)',
                  (aid, d['id'], d['attempt_count'] + 1, 'pending', attempt['backend'], now, now))
        self.bind(c, d, aid, tier='resolver', handoff_id=hid)
        self.store.close_questions(c, d['request_id'], 'handed-to-resolver', delegation_id=d['id'])
        approval = self.store.policy(c, d['chat_id'])['approvalPolicy'] == 'required' and actor != 'human'
        d = self.store.set_delegation(c, d, 'awaiting-approval' if approval else 'dispatched', attempt_id=aid,
                                      attempt_count=d['attempt_count'] + 1, max_attempts=d['attempt_count'] + 1)
        if req['status'] == 'awaiting-synthesis':
            self.store.set_request(c, req, 'delegated')
        self.store.pool.decide(c, d['request_id'], 'resolver', {'delegationId': d['id'], 'handoffId': hid, 'reason': reason,
                                                                'settings': {k: settings.get(k) for k in ('provider', 'model', 'reasoningEffort', 'fast')}},
                               source, 'human' if actor == 'human' else 'captured', 'resolver:' + hid)
        self.store.event(c, d['chat_id'], 'resolver-engaged', {'delegation': self.store.public_delegation(c, d), 'handoffId': hid,
                                                               'reason': reason, 'actor': actor, 'previousAttemptId': attempt['id']})
        self.store.op(c, 'resolver-engaged', delegationId=d['id'], handoffId=hid, actor=actor)
        return {'delegationId': d['id'], 'attemptId': aid, 'handoffId': hid, 'ownerEpoch': epoch,
                'status': d['status'], 'bundleHash': _digest(bundle)[:24]}

    def handoff(self, c, handoff_id):
        row = self.store.row(c, 'SELECT * FROM resolver_handoffs WHERE id=?', handoff_id)
        return {**row, 'settings': json.loads(row['settings']), 'bundle': json.loads(row['bundle'])} if row else None

    def attempt_view(self, c, attempt_id):
        """Execution contract handed to the backend with the attempt context."""
        binding = self.binding(c, attempt_id)
        if not binding:
            return {'tier': 'expert', 'binding': None, 'resolver': None, 'performerContext': None}
        manifest = self.store.row(c, 'SELECT * FROM execution_manifests WHERE id=?', binding['manifest_id']) if binding['manifest_id'] else None
        snapshot = self.restore(c, binding['snapshot_id']) if binding['snapshot_id'] else None
        resolver = self.handoff(c, binding['handoff_id']) if binding['tier'] == 'resolver' and binding['handoff_id'] else None
        return {'tier': binding['tier'],
                'binding': {'ownerEpoch': binding['owner_epoch'], 'taskRevision': binding['task_revision'],
                            'claimToken': binding['claim_token'], 'performerId': binding['performer_id'],
                            'employmentId': binding['employment_id'], 'sessionId': binding['session_id'],
                            'leaseUntil': binding['lease_until']},
                'resolver': {'agentId': binding['session_id'] or 'resolve-cq-' + attempt_id[4:], 'settings': resolver['settings'],
                             'handoffId': resolver['id'], 'bundle': resolver['bundle']} if resolver else None,
                'performerContext': {'manifest': {'id': manifest['id'], 'hash': manifest['hash'], 'skills': json.loads(manifest['skills']),
                                                  'authority': json.loads(manifest['authority'])} if manifest else None,
                                     'memorySnapshot': snapshot}}

    # -- projections -----------------------------------------------------------------------------------
    def conductor_view(self, c):
        """One logical conductor; its physical instances and their A/B sessions are listed, never counted as conductors."""
        sessions = []
        for row in c.execute('SELECT * FROM conductors ORDER BY created_at, ordinal'):
            state = json.loads(row['handoff'])
            for slot, native in sorted(state.get('sessions', {}).items()):
                sessions.append({'instanceId': row['id'], 'slot': slot, 'sessionRef': native, 'owner': state.get('owner') == slot,
                                 'epoch': state.get('epoch'), 'status': row['status'] if state.get('owner') == slot else 'standby',
                                 'turnId': row['turn_id'] if state.get('owner') == slot else None, 'chatId': row['chat_id']})
        assignments = c.execute('SELECT COUNT(*), MAX(seq) FROM assignment_log').fetchone()
        return {'id': 'logical-conductor', 'instanceCount': c.execute('SELECT COUNT(*) FROM conductors').fetchone()[0],
                'sessions': sessions, 'assignmentCount': assignments[0], 'lastAssignmentSeq': assignments[1]}

    def projection(self, c):
        """Control-center rows: each domain shows exactly one logical performer (or that none is hired)."""
        from conductor.queue import DELEGATION_TERMINAL
        domains = []
        policy_rows = {r['id']: json.loads(r['policy']) for r in c.execute('SELECT id, policy FROM chats')}
        default_policy = next(iter(policy_rows.values()), None)
        for domain in self.domains():
            employment = self.active(c, domain['id'])
            delegations = [dict(r) for r in c.execute(
                "SELECT d.* FROM delegations d JOIN entity_areas a ON a.kind='delegation' AND a.id=d.id"
                " WHERE json_extract(a.area, '$.domainId')=? ORDER BY d.updated_at DESC, d.id", (domain['id'],))]
            current = next((d for d in delegations if d['status'] not in DELEGATION_TERMINAL), None)
            recent = next((d for d in delegations if d['status'] in DELEGATION_TERMINAL), None)
            history = [{'employmentId': r['id'], 'performerId': r['performer_id'], 'performerName': r['name'],
                        'revision': r['revision'], 'status': r['status'], 'decisionRef': r['decision_ref'], 'actor': r['actor'],
                        'createdAt': r['created_at'], 'endedAt': r['ended_at'], 'endReason': r['end_reason']}
                       for r in c.execute('SELECT e.*, p.name FROM employments e JOIN performers p ON p.id=e.performer_id'
                                          ' WHERE e.domain_id=? ORDER BY e.created_at, e.revision', (domain['id'],))]
            sessions = []
            owner = employment['performer_id'] if employment else 'unhired:' + domain['id']
            for row in c.execute("SELECT * FROM exec_sessions WHERE owner_id=? ORDER BY created_at, id", (owner,)):
                task = None
                if row['current_attempt_id']:
                    d = self.store.row(c, 'SELECT d.id, d.title FROM delegations d JOIN attempts a ON a.delegation_id=d.id WHERE a.id=?',
                                       row['current_attempt_id'])
                    task = {'delegationId': d['id'], 'title': d['title'], 'attemptId': row['current_attempt_id']} if d else None
                settings = json.loads(row['settings'] or 'null') or {}
                sessions.append({'id': row['id'], 'tier': row['tier'], 'state': row['state'], 'task': task,
                                 'settings': {k: settings.get(k) for k in ('provider', 'model', 'reasoningEffort', 'fast')},
                                 'updatedAt': row['updated_at']})
            area = {'domainId': domain['id']}
            chat_id = (current or recent or {}).get('chat_id') or next(iter(policy_rows), None)
            policy = policy_rows.get(chat_id) if chat_id else default_policy
            domains.append({'domainId': domain['id'], 'domainName': domain['name'],
                            'employment': {'id': employment['id'], 'revision': employment['revision'], 'status': 'active',
                                           'decisionRef': employment['decision_ref'], 'authority': json.loads(employment['authority']),
                                           'skillScope': json.loads(employment['skill_scope']), 'hiredAt': employment['created_at']} if employment else None,
                            'status': 'hired' if employment else 'unhired',
                            'performer': {'id': employment['performer_id'], 'name': employment['performer_name']} if employment else None,
                            'currentTask': self._task_view(c, current) if current else None,
                            'recentResult': self._task_view(c, recent) if recent else None,
                            'sessions': sessions, 'history': history,
                            'resolver': self.resolver_state(c, area, policy, chat_id)})
        return {'domains': domains, 'conductor': self.conductor_view(c), 'policy': self.settings(c), 'fixedPolicy': FIXED,
                'deadLetters': len(self.dead_letters(c)),
                'skills': [{'id': r['id'], 'skillId': r['skill_id'], 'revision': r['revision'], 'layer': r['layer'],
                            'scopeId': r['scope_id'], 'status': r['status'], 'origin': r['origin']}
                           for r in c.execute('SELECT * FROM skill_revisions ORDER BY skill_id, revision')]}

    def _task_view(self, c, d):
        attempt = self.store.row(c, 'SELECT * FROM attempts WHERE id=?', d['attempt_id'])
        binding = self.binding(c, d['attempt_id'])
        wait = self.store.row(c, 'SELECT reason FROM attempt_waits WHERE attempt_id=?', d['attempt_id'])
        question = c.execute("SELECT 1 FROM questions WHERE delegation_id=? AND state='pending'", (d['id'],)).fetchone()
        spec = json.loads(d['spec'])
        reason = (wait['reason'] if wait else 'question' if question else
                  {'awaiting-approval': 'approval', 'ready': 'dispatch', 'dispatched': 'worker-start',
                   'cancel-requested': 'cancellation', 'awaiting-answer': 'question'}.get(d['status']))
        result = json.loads(d['result'] or 'null')
        return {'delegationId': d['id'], 'requestId': d['request_id'], 'chatId': d['chat_id'], 'title': d['title'],
                'goal': spec.get('goal') or d['title'], 'status': d['status'], 'version': d['version'],
                'stage': attempt['status'] if attempt else None, 'waitReason': reason,
                'attemptId': d['attempt_id'], 'attemptCount': d['attempt_count'], 'tier': binding['tier'] if binding else 'expert',
                'ownerEpoch': self.owner_view(c, d['id'])['owner_epoch'], 'taskRevision': self.owner_view(c, d['id'])['task_revision'],
                'progress': json.loads(attempt['progress'] or 'null') if attempt else None,
                'summary': result.get('summary') if isinstance(result, dict) else None,
                'error': json.loads(d['error'] or 'null'), 'updatedAt': d['updated_at'],
                'resolverHandoffs': [r[0] for r in c.execute('SELECT id FROM resolver_handoffs WHERE delegation_id=? ORDER BY created_at', (d['id'],))]}


def _within(path, root):
    path, root = path.strip('/'), root.strip('/')
    return root in ('', '.') or path == root or path.startswith(root + '/')
