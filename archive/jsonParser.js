// ─── jsonParser.js ───────────────────────────────────────────────────────────
// Robust JSON sanitiser and repair for AI-generated output.

/**
 * Sanitize raw text that may contain markdown fences, BOM, or control chars
 * inside string literals. Returns a string safe for JSON.parse.
 * @param {string} raw
 * @returns {string}
 */
export function sanitizeJson(raw) {
  let s = raw.trim().replace(/^\uFEFF/, '').replace(/^\`\`\`json?\s*/im,'').replace(/\s*\`\`\`\s*$/im,'');
  let out = '', inStr = false, isEscaped = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (isEscaped)   { out += ch; isEscaped = false; continue; }
    if (ch === '\\') { out += ch; isEscaped = true;  continue; }
    if (ch === '"')  { out += ch; inStr = !inStr; continue; }
    if (inStr) {
      if      (ch === '\n') out += '\\n';
      else if (ch === '\r') out += '\\r';
      else if (ch === '\t') out += '\\t';
      else                   out += ch;
    } else { out += ch; }
  }
  return out;
}

/**
 * Parse AI-generated JSON with multiple fallback repair strategies:
 *  1. Direct parse after sanitize + trailing comma fix
 *  2. Extract first `{` to end, then parse
 *  3. Bracket-balance repair (close unclosed strings/braces/brackets)
 *
 * @param {string} raw - Raw AI output (may include preamble, code fences, truncation)
 * @returns {import('./helpers.js').DemoStructure}
 * @throws {Error} If all repair strategies fail
 */
export function parseAIJson(raw) {
  const fix = s => s.replace(/,(\s*[}\]])/g, '$1');
  const attempts = [
    () => JSON.parse(fix(sanitizeJson(raw))),
    () => { const m = sanitizeJson(raw).match(/\{[\s\S]*/); if (!m) throw new Error('no {'); return JSON.parse(fix(m[0])); },
    () => {
      let s = fix(sanitizeJson(raw).match(/\{[\s\S]*/)?.[0] || '');
      let b=0, k=0, inS=false, e2=false;
      for (const ch of s) {
        if (e2)          { e2=false; continue; }
        if (ch==='\\') { e2=true;  continue; }
        if (ch==='"')    { inS=!inS; continue; }
        if (inS)         continue;
        if (ch==='{') b++; else if (ch==='}') b--;
        if (ch==='[') k++; else if (ch===']') k--;
      }
      if (inS) s+='"';
      while(k>0){s+=']';k--;} while(b>0){s+='}';b--;}
      return JSON.parse(fix(s));
    },
  ];
  for (const fn of attempts) { try { return fn(); } catch(_) {} }
  throw new Error('JSON repair failed — reduce products to 2 and retry.');
}
