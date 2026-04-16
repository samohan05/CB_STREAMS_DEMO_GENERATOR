// ─── prompt.js ───────────────────────────────────────────────────────────────
// AI prompt builder for generating Codebeamer demo JSON structures.
// v3: Explicit parent_stream_key derivation. PL aggregates from multiple libraries.
//     Any stream can include projects not present in any other stream.

/**
 * Build the Claude/AI prompt that generates a DemoStructure JSON.
 * @param {string} domain   - e.g. "MRI Systems"
 * @param {string} industry - e.g. "Medical Devices"
 * @param {number} n        - number of product lines (caps release_streams at 5)
 * @returns {string} The complete prompt text
 */
export function buildPrompt(domain, industry, n) {
  const relCount = Math.min(n, 5);
  return `Generate a Codebeamer ALM demo JSON for:
Domain: ${domain}
Industry: ${industry}

CRITICAL: Return ONLY raw valid JSON. No markdown. No backticks. No text outside JSON.
CRITICAL: All string values max 120 chars. No real newlines inside strings. Use \\n only in steps fields.
CRITICAL: project_key and stream_key max 8 alphanumeric/underscore chars. No spaces. No hyphens.
CRITICAL: No apostrophes in any string value.

HOW CODEBEAMER STREAMS WORK:
- Projects are created ONCE in the Initial Stream.
- Streams form a hierarchy: Library -> Product Line -> Transform -> Release.
- The SAME projects are ADDED to streams — this branches their tracker items.
- Each stream sees its own independent version of Requirements and Test Cases.
- Any stream can include projects from multiple other streams, plus unique projects of its own.
- Streams have an explicit parent (sourceStreamId) for derivation:
    Library streams: no parent (top-level)
    PL streams: no parent (they aggregate from multiple libraries independently)
    Transform streams: parent = a specific PL stream
    Release streams: parent = a specific Transform stream

Return this exact top-level structure:
{
  "domain_name": "short label",
  "projects": [],
  "library_streams": [],
  "product_line_streams": [],
  "transform_streams": [],
  "release_streams": []
}

PROJECT SHAPE (all projects defined here, created once in Initial Stream):
{
  "project_key": "MAXEIGHT",
  "project_name": "Meaningful Name (e.g. Magnet System Requirements)",
  "description": "What this project holds, max 80 chars",
  "requirements": [
    {
      "title": "The [component] shall [verb] [value+unit] per [standard]",
      "description": "One sentence technical context max 100 chars.",
      "priority": "High",
      "level": "System",
      "test_cases": [{
        "title": "Verify [aspect] under [condition]",
        "description": "Test objective max 80 chars.",
        "steps": "1. Setup per standard\\n2. Apply stimulus\\n3. Measure with instrument",
        "expected_result": "Specific measurable criterion with unit and tolerance"
      }]
    }
  ]
}

STREAM SHAPE (all stream tiers use this shape):
{
  "stream_key": "LIB_XXX",
  "stream_name": "Descriptive Stream Name",
  "description": "One sentence max 80 chars.",
  "project_keys": ["MAGSYS", "MAGPERF"],
  "parent_stream_key": null
}

STRICT QUANTITIES:
- projects: exactly 6 (3 subsystem domains x 2 requirement types each)
- library_streams: exactly 3, one per subsystem, each references its 2 projects
- product_line_streams: exactly 2, each references ALL 6 projects (aggregated view across all libraries)
- transform_streams: exactly 2, each references ALL 6 projects, each has parent_stream_key pointing to its specific PL
- release_streams: exactly ${relCount}, each references ALL 6 projects, each has parent_stream_key pointing to its specific Transform
- Each project: exactly 2 requirements, each requirement: exactly 1 test case
- Project pairs by requirement type: e.g. [Magnet System Req, Magnet Performance Req]

PARENT STREAM RULES (parent_stream_key values):
- library_streams: parent_stream_key = null (all 3 are top-level)
- product_line_streams: parent_stream_key = null (they aggregate independently)
- transform_streams[0]: parent_stream_key = product_line_streams[0].stream_key
- transform_streams[1]: parent_stream_key = product_line_streams[1].stream_key
- release_streams: each must set parent_stream_key to one of the transform stream_keys

CONTENT RULES:
- Use real standards: IEC 60601/62304 for medical, ISO 26262/AUTOSAR for automotive, DO-178C for avionics
- Requirements: shall-style with measurable values, units, tolerances
- Release stream_name: plausible fictional product names, never real trademarks
- All 3 library streams must cover DISTINCT technical subsystems of ${domain}
- All project_key and stream_key values must be globally unique`;
}
