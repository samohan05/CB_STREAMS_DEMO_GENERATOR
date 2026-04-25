#!/usr/bin/env node
// ─── CB Demo Generator Test Suite ────────────────────────────────────────────
// v2: Updated for new data model — top-level projects, streams with project_keys.
// Lightweight test runner — no framework dependencies, runs with `node cb_demo_core.test.js`

import { buildPythonScript, esc, safeV, countAll, buildStreamMap, sanitizeJson, parseAIJson, TIERS } from './cb_demo_core.js';

// ─── Mini test framework ─────────────────────────────────────────────────────
let passed = 0, failed = 0, skipped = 0;
const failures = [];
const currentGroup = [];

function describe(name, fn) { currentGroup.push(name); fn(); currentGroup.pop(); }
describe.skip = (name, fn) => {
  skipped++;
  console.log(`  ⏭  [SKIP] ${name}`);
};

function it(name, fn) {
  const fullName = [...currentGroup, name].join(' > ');
  try {
    fn();
    passed++;
    console.log(`  ✅ ${fullName}`);
  } catch (e) {
    failed++;
    failures.push({ name: fullName, error: e.message });
    console.log(`  ❌ ${fullName}`);
    console.log(`     → ${e.message}`);
  }
}

function expect(actual) {
  return {
    toBe(expected) {
      if (actual !== expected) throw new Error(`Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    },
    toEqual(expected) {
      if (JSON.stringify(actual) !== JSON.stringify(expected))
        throw new Error(`Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    },
    toContain(str) {
      if (typeof actual !== 'string' || !actual.includes(str))
        throw new Error(`Expected output to contain "${str}"`);
    },
    toMatch(regex) {
      if (typeof actual !== 'string' || !regex.test(actual))
        throw new Error(`Expected output to match ${regex}`);
    },
    not: {
      toContain(str) {
        if (typeof actual === 'string' && actual.includes(str))
          throw new Error(`Expected output NOT to contain "${str}"`);
      },
      toThrow() {
        try { actual(); } catch (_) { throw new Error('Expected function NOT to throw, but it did'); }
      }
    },
    toThrow() {
      let threw = false;
      try { actual(); } catch (_) { threw = true; }
      if (!threw) throw new Error('Expected function to throw, but it did not');
    }
  };
}

// ─── Minimal fixture: v3 format — top-level projects, streams with project_keys + parent_stream_key ──
const MINIMAL_STRUCTURE = {
  domain_name: "Test MRI Systems",
  projects: [
    {
      project_key: "MAGSYS",
      project_name: "Magnet System Req",
      description: "System-level magnet requirements",
      requirements: [{
        title: "The magnet shall maintain 3.0T field homogeneity",
        description: "Core field requirement per IEC 60601",
        priority: "High",
        level: "System",
        test_cases: [{
          title: "Verify field homogeneity at 3.0T",
          description: "Measure field uniformity across imaging volume",
          steps: "1. Setup per IEC 60601\\n2. Energize magnet\\n3. Measure with NMR probe",
          expected_result: "Field within +/- 0.5 ppm over 40cm DSV"
        }]
      }]
    },
    {
      project_key: "PLREQ",
      project_name: "Platform Requirements",
      description: "Platform-level requirements",
      requirements: [{
        title: "The platform shall support 64-channel RF reception",
        description: "RF channel count for Ingenia platform",
        test_cases: [{
          title: "Verify 64-channel RF reception",
          description: "Test RF channel count",
          steps: "1. Connect 64ch head coil\\n2. Acquire data",
          expected_result: "All 64 channels active with SNR > threshold"
        }]
      }]
    }
  ],
  library_streams: [{
    stream_key: "LIB_MAG",
    stream_name: "Magnet Library",
    description: "Shared magnet requirements",
    project_keys: ["MAGSYS"],
    parent_stream_key: null
  }],
  product_line_streams: [{
    stream_key: "PL_INGNIA",
    stream_name: "Ingenia Platform",
    description: "High-end MRI platform",
    project_keys: ["MAGSYS", "PLREQ"],
    parent_stream_key: null
  }],
  transform_streams: [],
  release_streams: []
};

// Extended fixture with full 4-tier hierarchy for parent_stream_key tests
const FULL_HIERARCHY = {
  domain_name: "Test Automotive",
  projects: [
    { project_key: "PWRREQ", project_name: "Powertrain System Req", description: "Powertrain reqs", requirements: [{ title: "Req1", description: "d", test_cases: [{ title: "TC1", description: "d", steps: "1. step", expected_result: "pass" }] }] },
    { project_key: "SAFEREQ", project_name: "Safety Req", description: "Safety reqs", requirements: [{ title: "Req2", description: "d", test_cases: [{ title: "TC2", description: "d", steps: "1. step", expected_result: "pass" }] }] },
  ],
  library_streams: [
    { stream_key: "LIB_PWR", stream_name: "Powertrain Library", description: "Powertrain lib", project_keys: ["PWRREQ"], parent_stream_key: null },
  ],
  product_line_streams: [
    { stream_key: "PL_SUV", stream_name: "SUV Platform", description: "SUV PL", project_keys: ["PWRREQ", "SAFEREQ"], parent_stream_key: null },
  ],
  transform_streams: [
    { stream_key: "TR_FORT", stream_name: "Fortuner Transform", description: "Fortuner config", project_keys: ["PWRREQ", "SAFEREQ"], parent_stream_key: "PL_SUV" },
  ],
  release_streams: [
    { stream_key: "REL_F25", stream_name: "Fortuner 2025", description: "2025 release", project_keys: ["PWRREQ", "SAFEREQ"], parent_stream_key: "TR_FORT" },
  ],
};

// ═══════════════════════════════════════════════════════════════════════════════
console.log('\n═══ CB Demo Generator — Test Suite (v3) ═══\n');

// ─── Helper Tests ────────────────────────────────────────────────────────────

describe('esc (string escaper)', () => {
  it('escapes double quotes', () => {
    expect(esc('say "hello"')).toBe('say \\"hello\\"');
  });
  it('escapes backslashes', () => {
    expect(esc('path\\to\\file')).toBe('path\\\\to\\\\file');
  });
  it('replaces newlines with spaces', () => {
    expect(esc('line1\nline2\r\nline3')).toBe('line1 line2 line3');
  });
  it('handles null/undefined gracefully', () => {
    expect(esc(null)).toBe('');
    expect(esc(undefined)).toBe('');
  });
});

describe('safeV (safe variable name)', () => {
  it('replaces non-alphanumeric chars with underscores', () => {
    expect(safeV('my-key.v2')).toBe('my_key_v2');
  });
  it('prefixes leading digits', () => {
    expect(safeV('3dModel')).toBe('_3dModel');
  });
  it('handles null/undefined', () => {
    expect(safeV(null)).toBe('x');
  });
});

describe('countAll (v3 data model)', () => {
  it('counts projects from top-level projects array', () => {
    const c = countAll(MINIMAL_STRUCTURE);
    expect(c.projects).toBe(2);
  });
  it('counts streams across all tiers', () => {
    const c = countAll(MINIMAL_STRUCTURE);
    expect(c.streams).toBe(2);  // 1 library + 1 PL
  });
  it('counts requirements from top-level projects', () => {
    const c = countAll(MINIMAL_STRUCTURE);
    expect(c.reqs).toBe(2);
  });
  it('counts test cases from top-level projects', () => {
    const c = countAll(MINIMAL_STRUCTURE);
    expect(c.tcs).toBe(2);
  });
  it('counts stream-project links (total project_keys across all streams)', () => {
    const c = countAll(MINIMAL_STRUCTURE);
    expect(c.streamProjectLinks).toBe(3);  // LIB has 1 key, PL has 2 keys
  });
  it('returns zeros for null input', () => {
    expect(countAll(null)).toEqual({streams:0,projects:0,reqs:0,tcs:0,streamProjectLinks:0});
  });
});

// ─── Python Script Output Tests ──────────────────────────────────────────────

const script = buildPythonScript(MINIMAL_STRUCTURE, 'https://cb.example.com', 'testuser', 'testpass');

describe('Phase 1A: Verifies field reference (PUT /v3/items/{id}/fields)', () => {
  it('generates set_verifies using PUT /v3/items/{itemId}/fields', () => {
    expect(script).toContain('_put(f"/v3/items/{tc_id}/fields"');
  });
  it('uses UpdateTrackerItemField payload with fieldValues array', () => {
    expect(script).toContain('"fieldValues": [{');
  });
  it('references VERIFIES_FIELD_ID constant (not hardcoded 17)', () => {
    expect(script).toContain('"fieldId": VERIFIES_FIELD_ID');
  });
  it('sets type to ChoiceFieldValue (not FieldReference)', () => {
    expect(script).toContain('"type": "ChoiceFieldValue"');
  });
  it('passes requirement ID with TrackerItemReference type in values array', () => {
    expect(script).toContain('"values": [{"id": req_id, "type": "TrackerItemReference"}]');
  });
  it('does NOT use FieldReference type', () => {
    expect(script).not.toContain('"type": "FieldReference"');
  });
  it('declares VERIFIES_FIELD_ID constant with default value 17', () => {
    expect(script).toMatch(/VERIFIES_FIELD_ID\s*=\s*17/);
  });
  it('does NOT use upstreamReferences', () => {
    expect(script).not.toContain('upstreamReferences');
  });
  it('does NOT reference POST /v3/associations', () => {
    expect(script).not.toContain('POST /v3/associations');
  });
  it('documents the fields API in the script header', () => {
    expect(script).toContain('PUT  /v3/items/{id}/fields');
  });
});

describe('Script structure', () => {
  it('starts with shebang line', () => {
    expect(script).toMatch(/^#!/);
  });
  it('imports requests library', () => {
    expect(script).toContain('import os, requests');
  });
  it('uses the provided CB URL', () => {
    expect(script).toContain('https://cb.example.com');
  });
  it('uses the provided username', () => {
    expect(script).toContain('testuser');
  });
  it('fetches initial stream ID at startup', () => {
    expect(script).toContain('_get("/v3/streams/initial")');
  });
  it('generates mk_stream calls for library streams', () => {
    expect(script).toContain('mk_stream("Magnet Library"');
  });
  it('generates mk_project calls with correct name', () => {
    expect(script).toContain('mk_project("Magnet System Req"');
  });
  it('generates mk_tracker calls for REQ and TC types', () => {
    expect(script).toContain('REQ_TYPE_ID');
    expect(script).toContain('TC_TYPE_ID');
  });
  it('generates mk_item calls for requirements', () => {
    expect(script).toContain('mk_item(');
  });
  it('calls set_verifies to link TC to REQ', () => {
    expect(script).toMatch(/set_verifies\(\s*tcid_/);
  });
  it('calls mk_stream_project to add projects to streams', () => {
    expect(script).toContain('mk_stream_project(');
  });
});

describe('v3 Architecture: 2-phase project/stream creation', () => {
  it('creates _project_ids lookup dict', () => {
    expect(script).toContain('_project_ids = {}');
  });
  it('has PHASE 1 header for project creation', () => {
    expect(script).toContain('PHASE 1: Create');
  });
  it('has PHASE 2 header for stream creation', () => {
    expect(script).toContain('PHASE 2: Create');
  });
  it('Phase 1 creates projects from top-level projects array', () => {
    // Both projects from the fixture should be created in Phase 1
    expect(script).toContain('mk_project("Magnet System Req"');
    expect(script).toContain('mk_project("Platform Requirements"');
  });
  it('Phase 1 stores project IDs in _project_ids dict', () => {
    expect(script).toContain('_project_ids["MAGSYS"]');
    expect(script).toContain('_project_ids["PLREQ"]');
  });
  it('Phase 2 stores stream IDs in _stream_ids dict', () => {
    expect(script).toContain('_stream_ids["LIB_MAG"]');
    expect(script).toContain('_stream_ids["PL_INGNIA"]');
  });
  it('Phase 2 creates streams with hierarchy', () => {
    expect(script).toContain('mk_stream("Magnet Library"');
    expect(script).toContain('mk_stream("Ingenia Platform"');
  });
  it('Phase 2 adds projects to streams via _project_ids lookup', () => {
    expect(script).toContain('_project_ids.get("MAGSYS")');
  });
  it('Phase 2 uses mk_stream_project with INITIAL_STREAM_ID', () => {
    expect(script).toContain('mk_stream_project(');
    expect(script).toContain('INITIAL_STREAM_ID');
  });
  it('tracks stream_project_links count', () => {
    expect(script).toContain('_counts["stream_project_links"] += 1');
  });
  it('includes stream_project_links in expected counts', () => {
    expect(script).toContain('"stream_project_links": 3');  // 1 + 2 = 3 from MINIMAL_STRUCTURE
  });
  it('projects are created BEFORE streams (Phase 1 before Phase 2)', () => {
    const phase1Pos = script.indexOf('PHASE 1');
    const phase2Pos = script.indexOf('PHASE 2');
    const firstMkProject = script.indexOf('mk_project("Magnet System Req"');
    const firstMkStream = script.indexOf('mk_stream("Magnet Library"');
    expect(phase1Pos < phase2Pos).toBe(true);
    expect(firstMkProject < firstMkStream).toBe(true);
  });
});

describe('Phase 1B: Stream hierarchy via sourceStreamId (v3 explicit parent)', () => {
  it('mk_stream accepts an optional source_id parameter', () => {
    expect(script).toContain('def mk_stream(name, desc="", source_id=None)');
  });
  it('passes sourceStreamId in the CreateStream body when source_id is provided', () => {
    expect(script).toContain('body["sourceStreamId"] = source_id');
  });
  it('sets isSourceStreamChecked to True when source_id is provided', () => {
    expect(script).toContain('body["isSourceStreamChecked"] = True');
  });
  it('initializes _stream_ids dict for explicit parent resolution', () => {
    expect(script).toContain('_stream_ids = {}');
  });
  it('does NOT use _tier_first_stream (v2 pattern removed)', () => {
    expect(script).not.toContain('_tier_first_stream');
  });
  it('library streams are created with no parent (None)', () => {
    expect(script).toMatch(/mk_stream\("Magnet Library".*,\s*None\)/);
  });
  it('PL streams with null parent_stream_key get None', () => {
    expect(script).toMatch(/mk_stream\("Ingenia Platform".*,\s*None\)/);
  });
  it('stores stream IDs in _stream_ids after creation', () => {
    expect(script).toContain('_stream_ids["LIB_MAG"]');
  });
  it('logs parent info in stream creation output', () => {
    expect(script).toContain('parent={source_id}');
  });
});

describe('v3 Explicit parent_stream_key derivation (full hierarchy)', () => {
  const fullScript = buildPythonScript(FULL_HIERARCHY, 'https://cb.test.com', 'admin', 'pass');
  it('Transform stream resolves parent from _stream_ids.get(PL key)', () => {
    expect(fullScript).toContain('_stream_ids.get("PL_SUV")');
  });
  it('Release stream resolves parent from _stream_ids.get(Transform key)', () => {
    expect(fullScript).toContain('_stream_ids.get("TR_FORT")');
  });
  it('Library streams have None parent', () => {
    expect(fullScript).toMatch(/mk_stream\("Powertrain Library".*,\s*None\)/);
  });
  it('PL streams with null parent have None', () => {
    expect(fullScript).toMatch(/mk_stream\("SUV Platform".*,\s*None\)/);
  });
  it('stores all stream keys in _stream_ids', () => {
    expect(fullScript).toContain('_stream_ids["LIB_PWR"]');
    expect(fullScript).toContain('_stream_ids["PL_SUV"]');
    expect(fullScript).toContain('_stream_ids["TR_FORT"]');
    expect(fullScript).toContain('_stream_ids["REL_F25"]');
  });
  it('counts all 4 streams in expected summary', () => {
    expect(fullScript).toContain('"streams": 4');
  });
  it('counts stream-project links correctly (1+2+2+2=7)', () => {
    expect(fullScript).toContain('"stream_project_links": 7');
  });
});

describe('buildStreamMap helper', () => {
  it('builds a lookup map from stream_key to Stream object', () => {
    const map = buildStreamMap(FULL_HIERARCHY);
    expect(map["LIB_PWR"].stream_name).toBe("Powertrain Library");
    expect(map["PL_SUV"].stream_name).toBe("SUV Platform");
    expect(map["TR_FORT"].stream_name).toBe("Fortuner Transform");
    expect(map["REL_F25"].stream_name).toBe("Fortuner 2025");
  });
  it('returns empty map for null input', () => {
    const map = buildStreamMap(null);
    expect(JSON.stringify(map)).toBe('{}');
  });
});

describe('Phase 1C: Secure credential handling', () => {
  it('imports os module for environment variables', () => {
    expect(script).toContain('import os,');
  });
  it('reads CB_URL from os.environ', () => {
    expect(script).toContain('os.environ.get("CB_URL"');
  });
  it('reads CB_USER from os.environ', () => {
    expect(script).toContain('os.environ.get("CB_USER"');
  });
  it('reads CB_PASS from os.environ', () => {
    expect(script).toContain('os.environ.get("CB_PASS"');
  });
  it('does NOT embed the actual password in the script', () => {
    expect(script).not.toContain('testpass');
  });
  it('CB_PASS line has NEVER hardcoded comment', () => {
    expect(script).toContain('NEVER hardcoded');
  });
  it('exits with clear message if credentials are missing', () => {
    expect(script).toContain('ERROR: Codebeamer credentials not set.');
    expect(script).toContain('sys.exit(1)');
  });
  it('shows env var instructions on missing credentials', () => {
    expect(script).toContain('CB_USER=');
    expect(script).toContain('CB_PASS=');
  });
  it('still embeds URL and username as convenience defaults', () => {
    expect(script).toContain('https://cb.example.com');
    expect(script).toContain('testuser');
  });
});

describe('Phase 1D: Retry wrapper with rate-limit handling', () => {
  it('declares MAX_RETRIES constant', () => {
    expect(script).toMatch(/MAX_RETRIES\s*=\s*4/);
  });
  it('declares BACKOFF_BASE constant (seconds)', () => {
    expect(script).toMatch(/BACKOFF_BASE\s*=\s*1\.0/);
  });
  it('declares RETRY_STATUSES set with 429 and 5xx codes', () => {
    expect(script).toContain('RETRY_STATUSES');
    expect(script).toContain('429');
    expect(script).toContain('500');
    expect(script).toContain('502');
    expect(script).toContain('503');
    expect(script).toContain('504');
  });
  it('defines _request(method, path, body=None) function', () => {
    expect(script).toContain('def _request(method, path, body=None)');
  });
  it('uses getattr(requests, method) for dynamic dispatch', () => {
    expect(script).toContain('getattr(requests, method)');
  });
  it('implements exponential backoff with BACKOFF_BASE * (2 ** attempt)', () => {
    expect(script).toContain('BACKOFF_BASE * (2 ** attempt)');
  });
  it('respects Retry-After header on 429 responses', () => {
    expect(script).toContain('Retry-After');
  });
  it('logs retry attempts with status code and wait time', () => {
    expect(script).toMatch(/retry.*\{attempt\+1\}.*\{MAX_RETRIES\}/);
  });
  it('_get/_post/_put delegate to _request', () => {
    expect(script).toContain('def _get(path):           return _request("get", path)');
    expect(script).toContain('def _post(path, body):    return _request("post", path, body)');
    expect(script).toContain('def _put(path, body):     return _request("put", path, body)');
  });
  it('does NOT have hardcoded time.sleep(0.07) in mk_item', () => {
    const mkItemMatch = script.match(/def mk_item[\s\S]*?(?=\ndef )/);
    if (!mkItemMatch) throw new Error('Could not find mk_item function');
    expect(mkItemMatch[0]).not.toContain('time.sleep(0.07)');
  });
});

// ─── Phase 2 Tests ──────────────────────────────────────────────────────────

describe('Phase 2C: Bug fixes and alignment', () => {
  it('project keyName truncation uses key[:8] not key[:16]', () => {
    expect(script).toContain('key[:8]');
    expect(script).not.toContain('key[:16]');
  });
  it('Retry-After parse is guarded with try/except', () => {
    expect(script).toContain('try: wait = float(r.headers.get("Retry-After"');
    expect(script).toContain('except (ValueError, TypeError): pass');
  });
  it('script header references ChoiceFieldValue (not FieldReference)', () => {
    const headerMatch = script.match(/"""[\s\S]*?"""/);
    if (!headerMatch) throw new Error('Could not find script header docstring');
    expect(headerMatch[0]).toContain('ChoiceFieldValue');
    expect(headerMatch[0]).not.toContain('FieldReference');
  });
});

// ─── Phase 3A Tests ─────────────────────────────────────────────────────────

describe('Phase 3A: Idempotency (--dry-run, --clean, find_project)', () => {
  it('imports argparse module', () => {
    expect(script).toContain('import os, requests, time, sys, argparse');
  });
  it('creates ArgumentParser with --dry-run flag', () => {
    expect(script).toContain('parser.add_argument("--dry-run"');
    expect(script).toContain('action="store_true"');
  });
  it('creates ArgumentParser with --clean flag', () => {
    expect(script).toContain('parser.add_argument("--clean"');
  });
  it('parses args into DRY_RUN and CLEAN globals', () => {
    expect(script).toContain('DRY_RUN = args.dry_run');
    expect(script).toContain('CLEAN   = args.clean');
  });
  it('defines find_project(key) function', () => {
    expect(script).toContain('def find_project(key)');
  });
  it('find_project scans GET /v3/projects for matching keyName', () => {
    expect(script).toContain('_get("/v3/projects")');
    expect(script).toContain('p.get("keyName") == key');
  });
  it('defines delete_project(pid) function', () => {
    expect(script).toContain('def delete_project(pid)');
  });
  it('delete_project uses DELETE /v3/projects/{id}', () => {
    expect(script).toContain('_delete(f"/v3/projects/{pid}")');
  });
  it('defines _delete helper that delegates to _request', () => {
    expect(script).toContain('def _delete(path):');
    expect(script).toContain('_request("delete", path)');
  });
  it('mk_project checks find_project before creating', () => {
    expect(script).toContain('existing = find_project(key[:8])');
  });
  it('mk_project reuses existing project when not in clean mode', () => {
    expect(script).toContain('already exists, reusing');
  });
  it('mk_project deletes existing project when CLEAN is set', () => {
    expect(script).toContain('if CLEAN:');
    expect(script).toContain('delete_project(existing)');
  });
  it('mk_project respects DRY_RUN flag', () => {
    const mkProjMatch = script.match(/def mk_project[\s\S]*?(?=\ndef )/);
    if (!mkProjMatch) throw new Error('Could not find mk_project function');
    expect(mkProjMatch[0]).toContain('if DRY_RUN:');
  });
  it('mk_tracker respects DRY_RUN flag', () => {
    const match = script.match(/def mk_tracker[\s\S]*?(?=\ndef )/);
    if (!match) throw new Error('Could not find mk_tracker function');
    expect(match[0]).toContain('if DRY_RUN:');
  });
  it('mk_item respects DRY_RUN flag', () => {
    const match = script.match(/def mk_item[\s\S]*?(?=\ndef )/);
    if (!match) throw new Error('Could not find mk_item function');
    expect(match[0]).toContain('if DRY_RUN:');
  });
  it('set_verifies respects DRY_RUN flag', () => {
    const match = script.match(/def set_verifies[\s\S]*?(?=\ndef )/);
    if (!match) throw new Error('Could not find set_verifies function');
    expect(match[0]).toContain('if DRY_RUN:');
  });
  it('mk_stream respects DRY_RUN flag', () => {
    const match = script.match(/def mk_stream[\s\S]*?(?=\ndef )/);
    if (!match) throw new Error('Could not find mk_stream function');
    expect(match[0]).toContain('if DRY_RUN:');
  });
  it('mk_stream_project respects DRY_RUN flag', () => {
    const match = script.match(/def mk_stream_project[\s\S]*?(?=\n\n|`)/);
    if (!match) throw new Error('Could not find mk_stream_project function');
    expect(match[0]).toContain('if DRY_RUN:');
  });
  it('prints DRY-RUN banner when flag is set', () => {
    expect(script).toContain('DRY-RUN MODE');
  });
  it('prints CLEAN banner when flag is set', () => {
    expect(script).toContain('CLEAN MODE');
  });
  it('skips initial stream fetch in DRY_RUN mode', () => {
    expect(script).toContain('INITIAL_STREAM_ID = None');
    expect(script).toContain('[DRY-RUN] Skipping initial stream fetch');
  });
  it('documents GET /v3/projects and DELETE in API header', () => {
    expect(script).toContain('GET  /v3/projects');
    expect(script).toContain('DELETE /v3/projects/{id}');
  });
});

// ─── JSON Parser Tests ───────────────────────────────────────────────────────

describe('sanitizeJson', () => {
  it('strips markdown code fences', () => {
    const input = '```json\n{"a": 1}\n```';
    expect(sanitizeJson(input)).toBe('{"a": 1}');
  });
  it('escapes real newlines inside string values', () => {
    const input = '{"text": "line1\nline2"}';
    const result = sanitizeJson(input);
    expect(() => JSON.parse(result)).not.toThrow();
  });
  it('strips BOM character', () => {
    const input = '\uFEFF{"a": 1}';
    expect(sanitizeJson(input)).toBe('{"a": 1}');
  });
});

describe('parseAIJson', () => {
  it('parses valid JSON directly', () => {
    const result = parseAIJson('{"domain_name": "MRI"}');
    expect(result.domain_name).toBe('MRI');
  });
  it('handles trailing commas', () => {
    const result = parseAIJson('{"a": 1, "b": 2,}');
    expect(result.a).toBe(1);
  });
  it('handles preamble text before JSON', () => {
    const result = parseAIJson('Here is the JSON: {"a": 1}');
    expect(result.a).toBe(1);
  });
  it('repairs truncated JSON with missing closing braces', () => {
    const result = parseAIJson('{"a": {"b": 1}');
    expect(result.a.b).toBe(1);
  });
  it('throws on completely unparseable input', () => {
    expect(() => parseAIJson('not json at all')).toThrow();
  });
});

// ─── Phase 3B Tests ─────────────────────────────────────────────────────────

describe('Phase 3B: Auto-discovery (tracker types + Verifies field)', () => {
  it('generates discover_tracker_types function', () => {
    expect(script).toContain('def discover_tracker_types()');
  });
  it('discover_tracker_types calls GET /v3/trackers/types', () => {
    expect(script).toContain('_get("/v3/trackers/types")');
  });
  it('discover_tracker_types scans for "requirement" in type name', () => {
    expect(script).toContain('"requirement" in name');
  });
  it('discover_tracker_types scans for "test" and "case" in type name', () => {
    expect(script).toContain('"test" in name and "case" in name');
  });
  it('discover_tracker_types returns tuple (req_id, tc_id)', () => {
    expect(script).toContain('return req_id, tc_id');
  });
  it('discover_tracker_types returns (None, None) on failure', () => {
    expect(script).toContain('return None, None');
  });
  it('generates discover_verifies_field function', () => {
    expect(script).toContain('def discover_verifies_field(tc_tracker_id, project_id)');
  });
  it('discover_verifies_field creates a temp TC item', () => {
    expect(script).toContain('_discover_verifies_temp');
  });
  it('discover_verifies_field reads fields via GET /v3/items/{id}/fields', () => {
    expect(script).toContain('_get(f"/v3/items/{temp_id}/fields")');
  });
  it('discover_verifies_field looks for "verif" in field name', () => {
    expect(script).toContain('"verif" in name');
  });
  it('discover_verifies_field cleans up temp item in finally block', () => {
    expect(script).toContain('_delete(f"/v3/items/{temp_id}")');
  });
  it('calls discover_tracker_types at startup when not DRY_RUN', () => {
    expect(script).toContain('_req_type, _tc_type = discover_tracker_types()');
  });
  it('updates REQ_TYPE_ID from discovery result', () => {
    expect(script).toContain('if _req_type: REQ_TYPE_ID = _req_type');
  });
  it('updates TC_TYPE_ID from discovery result', () => {
    expect(script).toContain('if _tc_type:  TC_TYPE_ID  = _tc_type');
  });
  it('falls back to defaults when discovery fails', () => {
    expect(script).toContain('warn(f"Using defaults: REQ_TYPE_ID={REQ_TYPE_ID}, TC_TYPE_ID={TC_TYPE_ID}")');
  });
  it('skips discovery in DRY_RUN mode', () => {
    expect(script).toContain('[DRY-RUN] Skipping auto-discovery, using defaults');
  });
  it('initializes _verifies_discovered flag', () => {
    expect(script).toContain('_verifies_discovered = False');
  });
  it('triggers Verifies field discovery after first TC tracker creation', () => {
    expect(script).toContain('if not _verifies_discovered and');
  });
  it('calls discover_verifies_field with TC tracker and project IDs', () => {
    expect(script).toContain('_vf = discover_verifies_field(');
  });
  it('updates VERIFIES_FIELD_ID from lazy discovery result', () => {
    expect(script).toContain('if _vf: VERIFIES_FIELD_ID = _vf');
  });
  it('marks _verifies_discovered = True after first attempt', () => {
    const discoveredTrue = script.indexOf('_verifies_discovered = True');
    expect(discoveredTrue > 0).toBe(true);
  });
  it('documents GET /v3/trackers/types in script header', () => {
    expect(script).toContain('GET  /v3/trackers/types');
  });
  it('documents GET /v3/items/{id}/fields for discovery in script header', () => {
    expect(script).toContain('discover Verifies field ID');
  });
  it('keeps REQ_TYPE_ID = 5 as default constant', () => {
    expect(script).toContain('REQ_TYPE_ID          = 5');
  });
  it('keeps TC_TYPE_ID = 102 as default constant', () => {
    expect(script).toContain('TC_TYPE_ID           = 102');
  });
  it('keeps VERIFIES_FIELD_ID = 17 as default constant', () => {
    expect(script).toContain('VERIFIES_FIELD_ID    = 17');
  });
});

// ─── Phase 3C Tests ─────────────────────────────────────────────────────────

describe('Phase 3C: Validation and Summary', () => {
  it('initializes _counts dict with all seven categories', () => {
    expect(script).toContain('"stream_project_links": 0');
  });
  it('initializes _errors list for failure tracking', () => {
    expect(script).toContain('_errors = []');
  });
  it('increments streams count after mk_stream', () => {
    expect(script).toContain('_counts["streams"] += 1');
  });
  it('increments projects count after mk_project', () => {
    expect(script).toContain('_counts["projects"] += 1');
  });
  it('increments trackers count after mk_tracker', () => {
    expect(script).toContain('_counts["trackers"] += 1');
  });
  it('increments requirements count after mk_item for REQ', () => {
    expect(script).toContain('_counts["requirements"] += 1');
  });
  it('increments test_cases count after mk_item for TC', () => {
    expect(script).toContain('_counts["test_cases"] += 1');
  });
  it('increments verifies count after set_verifies', () => {
    expect(script).toContain('_counts["verifies"] += 1');
  });
  it('increments stream_project_links count', () => {
    expect(script).toContain('_counts["stream_project_links"] += 1');
  });
  it('appends to _errors when stream creation fails', () => {
    expect(script).toContain('_errors.append(("stream"');
  });
  it('appends to _errors when project creation fails', () => {
    expect(script).toContain('_errors.append(("project"');
  });
  it('appends to _errors when requirement creation fails', () => {
    expect(script).toContain('_errors.append(("requirement"');
  });
  it('prints EXECUTION SUMMARY header', () => {
    expect(script).toContain('EXECUTION SUMMARY');
  });
  it('defines expected counts dict from generation-time values', () => {
    expect(script).toContain('expected = {"streams":');
  });
  it('expected counts match MINIMAL_STRUCTURE (2 streams)', () => {
    expect(script).toContain('"streams": 2');
  });
  it('expected counts match MINIMAL_STRUCTURE (2 projects)', () => {
    expect(script).toContain('"projects": 2');
  });
  it('expected counts match MINIMAL_STRUCTURE (4 trackers = 2 projects * 2)', () => {
    expect(script).toContain('"trackers": 4');
  });
  it('expected counts match MINIMAL_STRUCTURE (2 requirements)', () => {
    expect(script).toContain('"requirements": 2');
  });
  it('expected counts match MINIMAL_STRUCTURE (2 test cases)', () => {
    expect(script).toContain('"test_cases": 2');
  });
  it('expected counts match MINIMAL_STRUCTURE (3 stream-project links)', () => {
    expect(script).toContain('"stream_project_links": 3');
  });
  it('prints summary rows with Category/Actual/Expected/Status headers', () => {
    expect(script).toContain("'Category'");
    expect(script).toContain("'Actual'");
    expect(script).toContain("'Expected'");
  });
  it('includes Stream-Proj row in summary table', () => {
    expect(script).toContain('"Stream-Proj"');
  });
  it('compares actual vs expected and flags MISSING items', () => {
    expect(script).toContain('"MISSING"');
  });
  it('prints all_ok success message when everything matches', () => {
    expect(script).toContain('All items created successfully.');
  });
  it('prints dry-run message in DRY_RUN mode', () => {
    expect(script).toContain('Dry-run complete');
  });
  it('prints failure message when items are missing', () => {
    expect(script).toContain('Some items failed');
  });
  it('prints error details with category and name', () => {
    expect(script).toContain('{cat.upper()}');
  });
  it('still prints Next steps in CB UI', () => {
    expect(script).toContain('Next steps in CB UI');
  });
});

// ─── Code Review Fixes ──────────────────────────────────────────────────────

describe('Code review fixes', () => {
  it('tracks tracker failures in _errors list (REQ tracker)', () => {
    expect(script).toContain('_errors.append(("tracker", "Requirements for');
  });
  it('tracks tracker failures in _errors list (TC tracker)', () => {
    expect(script).toContain('_errors.append(("tracker", "Test Cases for');
  });
  it('set_verifies returns True on success', () => {
    expect(script).toContain('return True');
  });
  it('set_verifies returns False on failure', () => {
    expect(script).toContain('return False');
  });
  it('verifies count only increments when set_verifies succeeds', () => {
    expect(script).toContain('if set_verifies(');
    expect(script).toContain(': _counts["verifies"] += 1');
  });
  it('does NOT have unconditional verifies count increment', () => {
    const lines = script.split('\n');
    const badPattern = lines.some((line, i) => {
      return line.trim() === '_counts["verifies"] += 1' &&
             i > 0 && !lines[i-1].includes('set_verifies');
    });
    expect(badPattern).toBe(false);
  });
});

// ─── Streams concept correctness ────────────────────────────────────────────

describe('Correct CB streams model', () => {
  it('script docstring mentions projects created ONCE in Initial Stream', () => {
    const headerMatch = script.match(/"""[\s\S]*?"""/);
    if (!headerMatch) throw new Error('Could not find docstring');
    expect(headerMatch[0]).toContain('Initial Stream');
  });
  it('projects are NOT created inside stream loops', () => {
    // In Phase 2 (after PHASE 2 marker), there should be NO mk_project calls
    const phase2Start = script.indexOf('PHASE 2');
    if (phase2Start < 0) throw new Error('Could not find PHASE 2 marker');
    const phase2Code = script.substring(phase2Start);
    expect(phase2Code).not.toContain('mk_project(');
  });
  it('mk_tracker is NOT called inside stream loops', () => {
    const phase2Start = script.indexOf('PHASE 2');
    if (phase2Start < 0) throw new Error('Could not find PHASE 2 marker');
    const phase2Code = script.substring(phase2Start);
    expect(phase2Code).not.toContain('mk_tracker(');
  });
  it('mk_item is NOT called inside stream loops', () => {
    const phase2Start = script.indexOf('PHASE 2');
    if (phase2Start < 0) throw new Error('Could not find PHASE 2 marker');
    const phase2Code = script.substring(phase2Start);
    expect(phase2Code).not.toContain('mk_item(');
  });
  it('INITIAL_STREAM_ID response is parsed for dict format', () => {
    expect(script).toContain('isinstance(INITIAL_STREAM_ID, dict)');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
console.log(`\n═══ Results: ${passed} passed, ${failed} failed, ${skipped} skipped ═══`);
if (failures.length) {
  console.log('\nFailures:');
  failures.forEach((f, i) => console.log(`  ${i+1}. ${f.name}\n     ${f.error}`));
}
process.exit(failed > 0 ? 1 : 0);
