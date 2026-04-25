// ─── helpers.js ──────────────────────────────────────────────────────────────
// Pure utility functions used by prompt builder, Python builder, and UI.
// v3: Streams have parent_stream_key for explicit derivation chain.
//     PL streams aggregate projects from multiple library streams.
//     Any stream can have projects not in any other stream.

import { TIERS } from './templates.js';

/**
 * @typedef {Object} TestCase
 * @property {string} title
 * @property {string} description
 * @property {string} steps
 * @property {string} expected_result
 */

/**
 * @typedef {Object} Requirement
 * @property {string}     title
 * @property {string}     description
 * @property {string}     priority
 * @property {string}     level
 * @property {TestCase[]} test_cases
 */

/**
 * @typedef {Object} Project
 * @property {string}        project_key
 * @property {string}        project_name
 * @property {string}        description
 * @property {Requirement[]} requirements
 */

/**
 * @typedef {Object} Stream
 * @property {string}      stream_key
 * @property {string}      stream_name
 * @property {string}      description
 * @property {string[]}    project_keys        - References to project_key values in the top-level projects array
 * @property {string|null} parent_stream_key   - Key of the parent stream (null for top-level library streams)
 */

/**
 * @typedef {Object} DemoStructure
 * @property {string}    domain_name
 * @property {Project[]} projects             - All projects (created once in Initial Stream)
 * @property {Stream[]}  library_streams
 * @property {Stream[]}  product_line_streams
 * @property {Stream[]}  transform_streams
 * @property {Stream[]}  release_streams
 */

/**
 * @typedef {Object} DemoCounts
 * @property {number} streams
 * @property {number} projects
 * @property {number} reqs
 * @property {number} tcs
 * @property {number} streamProjectLinks  - Total project-to-stream additions
 */

/**
 * Escape a string for safe embedding in Python string literals.
 * @param {string} s
 * @returns {string}
 */
export const esc  = s => (s||"").replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r?\n/g," ").trim();

/**
 * Convert a string to a safe Python variable name.
 * @param {string} s
 * @returns {string}
 */
export const safeV = s => (s||"x").replace(/[^a-zA-Z0-9]/g,"_").replace(/^(\d)/,"_$1");

/**
 * Count all streams, projects, requirements, test cases, and stream-project links.
 * @param {DemoStructure|null} s
 * @returns {DemoCounts}
 */
export const countAll = s => {
  if (!s) return { streams: 0, projects: 0, reqs: 0, tcs: 0, streamProjectLinks: 0 };
  const projects = s.projects || [];
  let reqs = 0, tcs = 0;
  projects.forEach(p => {
    (p.requirements || []).forEach(r => {
      reqs++;
      tcs += (r.test_cases || []).length;
    });
  });
  let streams = 0, streamProjectLinks = 0;
  TIERS.forEach(t => {
    (s[t.key] || []).forEach(st => {
      streams++;
      streamProjectLinks += (st.project_keys || []).length;
    });
  });
  return { streams, projects: projects.length, reqs, tcs, streamProjectLinks };
};

/**
 * Build a lookup map from stream_key to Stream object across all tiers.
 * @param {DemoStructure} s
 * @returns {Record<string, Stream>}
 */
export const buildStreamMap = s => {
  const map = {};
  if (!s) return map;
  TIERS.forEach(t => {
    (s[t.key] || []).forEach(st => {
      if (st.stream_key) map[st.stream_key] = st;
    });
  });
  return map;
};
