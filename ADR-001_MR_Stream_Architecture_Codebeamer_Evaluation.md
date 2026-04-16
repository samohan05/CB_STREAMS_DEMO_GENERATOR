# ADR-001: Philips MR 4-Tier Stream Architecture — Codebeamer Applicability Evaluation

**Status:** Proposed  
**Date:** April 15, 2026  
**Deciders:** Sailesh Mohan, MR Configuration Management team, Codebeamer implementation leads  
**Evaluator:** Implementation Specialist (3+ decades ALM/Codebeamer experience)

---

## Context

Philips MR manages a complex product portfolio (Ingenia, BlueSeal, MRx, Elition, Ambition, coils, software, therapy systems) and is proposing a 4-tier stream-based configuration management architecture originally conceived around Polarion Streams with Pure Variants. The question is whether this strategy translates well to **PTC Codebeamer** as the target ALM platform for an enterprise-grade implementation.

Codebeamer's public and internal APIs (v3.0) confirm native support for streams, including hierarchical stream creation from source streams, stream baselines, descendant stream traversal, project-to-stream assignment, and merge request workflows. This is a strong foundation — but there are critical differences from Polarion that must be addressed.

---

## Decision

**The 4-tier strategy is fundamentally sound and maps well to Codebeamer's architecture, but requires adaptation in three areas: Transform Stream automation, merge-back workflows, and variant management tooling.** The strategy should be adopted with the modifications outlined below.

---

## Tier-by-Tier Evaluation

### Tier 1: Library Streams — ✅ Strong Fit

| Dimension | Assessment |
|-----------|------------|
| Codebeamer support | **Native** — Streams can hold multiple projects; shared trackers can be grouped here |
| API coverage | Full — `POST /v3/streams/stream` with `sourceStreamId`, `PUT /v3/streams/{streamId}/projects` for project assignment |
| Complexity | Low |
| Risk | Low |

Codebeamer streams natively support the concept of library streams. You can create a top-level stream, assign shared projects (e.g., "Common Requirements," "Regulatory Standards," "Shared Test Specifications") to it, and all downstream streams derived from it inherit those projects. The `sourceStreamId` parameter on stream creation establishes the parent-child relationship cleanly.

**Recommendation:** Implement as proposed. Use Codebeamer's color-coding (the `color` field on streams) to visually distinguish library streams from product streams in the UI. Consider creating separate library streams per domain (e.g., "Regulatory Library," "Coil Interface Library") rather than one monolithic library, to keep merge scopes manageable.

---

### Tier 2: Product Line (PL) Streams — ✅ Strong Fit

| Dimension | Assessment |
|-----------|------------|
| Codebeamer support | **Native** — Derived streams with project inheritance |
| API coverage | Full — `GET /v3/streams/{streamId}/descendants` for hierarchy navigation |
| Complexity | Low–Medium |
| Risk | Low |

Deriving PL streams from Library streams is straightforward. Codebeamer's stream creation from a source stream automatically copies all projects and trackers from the parent, which is exactly the behavior needed. PL-specific artifacts (trackers, requirements, test cases) can then be added to the PL stream without affecting the library.

**Recommendation:** Implement as proposed. Establish a naming convention early (e.g., `LIB-MR-Common → PL-Ingenia`, `LIB-MR-Common → PL-BlueSeal`) to maintain clarity as the hierarchy grows. Use stream baselines (`GET /v3/streams/{streamId}/baselines`) to snapshot PL states before creating product-level derivatives.

---

### Tier 3: Transform Streams — ⚠️ Requires Significant Adaptation

| Dimension | Assessment |
|-----------|------------|
| Codebeamer support | **Partial** — No native Pure Variants integration for parametric substitution |
| API coverage | Stream creation is supported; automated transformation is not |
| Complexity | **High** |
| Risk | **Medium–High** |

This is the most significant gap. The original strategy relies on Pure Variants to automatically transform generic parameters from PL streams into product-specific values — creating read-only, product-specific streams without manual effort. Codebeamer does **not** have a native Pure Variants integration equivalent to what Polarion offers.

**Options for Transform Stream implementation in Codebeamer:**

**Option A: API-driven transformation pipeline (Recommended)**

Build a custom automation layer using Codebeamer's REST API that:
1. Creates a new stream from the PL source stream (`POST /v3/streams/stream`)
2. Iterates through all tracker items in the new stream (`GET /v3/items/query`)
3. Applies parametric substitutions via item field updates (`PUT /v3/items/{itemId}`)
4. Locks the stream or sets permissions to enforce read-only behavior

This can be triggered by CI/CD pipelines or scheduled jobs. Codebeamer's Working-Set APIs (`POST /v3/jobs/working-set-update`) and merge APIs (`POST /merge-requests/create`, `POST /merge-requests/merge-all`) provide the mechanics for controlled propagation.

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium–High |
| Maintainability | Good — API-based, version-controllable |
| Automation | Full, once built |
| Pure Variants parity | ~80% — lacks the UI-driven feature model, but achieves the functional outcome |

**Option B: Pure Variants external integration**

Pure Variants does have a Codebeamer connector (Pure Variants Enterprise for ALM). If the organization is already committed to Pure Variants, this connector can be explored. However, as of the latest PTC documentation, the integration maturity with Codebeamer's stream model is not at the same level as with Polarion.

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium (if connector works well) to High (if customization needed) |
| Vendor dependency | High |
| Automation | High (if configured) |
| Pure Variants parity | 90%+ |

**Option C: Manual stream creation with template-based guidance**

For smaller portfolios or initial rollout, create transform streams manually by deriving from PL streams and hand-editing parametric values. This is the lowest-effort option but does not scale.

**Recommendation:** Start with Option A for the pilot product line, with a clear path to evaluate Option B if Pure Variants is already in the toolchain. Do not attempt Option C beyond a proof-of-concept.

---

### Tier 4: Product Release / Variant Streams — ✅ Good Fit with Caveats

| Dimension | Assessment |
|-----------|------------|
| Codebeamer support | **Native** — Stream hierarchy + baselines |
| API coverage | Full — baselines, branches, working sets |
| Complexity | Medium |
| Risk | Low–Medium |

Codebeamer supports this tier well. Each product release can be a stream derived from the product (or transform) stream, and baselines (`POST /v3/baselines`) freeze the state at release time. Market/region variants can be additional derived streams.

The branch API (`GET /v3/branches/{branchId}/item`, `GET /v3/trackers/{trackerId}/branches`) supports tracker-level branching for variant-specific delta requirements.

**Caveat:** The deck notes that "latest product requirements can't flow back to PL streams automatically — requires manual merge." Codebeamer's merge request APIs (`POST /merge-requests/create`, `POST /merge-requests/diff`, `POST /merge-requests/merge-all`) provide a structured merge-back workflow, but it is indeed not automatic. This is a conscious trade-off and is actually preferable for regulated medical device development, where uncontrolled upstream propagation would be a compliance risk.

**Recommendation:** Implement as proposed. Leverage Codebeamer's merge request workflow for controlled merge-back rather than seeking full automation. For IEC 62304 / FDA 21 CFR Part 11 compliance, the manual review gate on merge-back is a feature, not a bug.

---

## Cross-Cutting Concerns

### Traceability Across Stream Boundaries

Codebeamer's association API (`POST /v3/associations`, association types including "derived from," "related to," "depends on") provides cross-stream traceability. Items in a product release stream can trace back to PL requirements and up to library-level standards. This is critical for medical device regulatory submissions (IEC 62304 traceability matrices).

**Action needed:** Define the association type taxonomy before implementation. Typical taxonomy for MR:
- `derived from` — requirement decomposition across tiers
- `verified by` — test case to requirement
- `implements` — design item to requirement
- `constrained by` — regulatory standard to requirement

### Test Run Reuse

The deck correctly flags this as a gap. Codebeamer's test management (test cases, test runs, test configurations) does not natively support "test run inheritance" across streams. Test *cases* can be shared (they live in trackers that propagate with streams), but test *runs* and *results* are stream-specific.

**Mitigation:** Use Codebeamer's reporting and review APIs to create cross-stream test coverage dashboards. For reusable test evidence (important for regulatory submissions), establish a convention where test runs reference the source test case's global ID, enabling cross-stream aggregation via `POST /v3/items/query` with cbQL.

### Performance at Scale

With the Philips MR portfolio, you could easily reach 50–100+ streams, each containing 10–20 projects with thousands of tracker items. Codebeamer's API has rate limiting (`429 Too Many Requests` responses confirmed in the API spec), and bulk operations on large stream hierarchies may need to be staged.

**Mitigation:** Use background jobs (`POST /v3/jobs/working-set-update`) for bulk propagation rather than synchronous API calls. Plan for incremental rather than full-hierarchy updates.

### Third-Party Supplier Collaboration

The deck flags this for further exploration. Codebeamer supports project-level permissions and role-based access, so supplier-facing projects can be included in streams with restricted visibility. The deployment/export APIs (`POST /v3/deployment/export`, `POST /v3/export/items`) enable controlled data exchange with suppliers who may use different ALM tools.

---

## Trade-off Analysis

| Dimension | Polarion (Original Strategy) | Codebeamer (Adapted Strategy) |
|-----------|------------------------------|-------------------------------|
| Stream hierarchy | Native, mature | Native, well-supported |
| Pure Variants integration | Tight, native | Requires custom integration or external connector |
| Merge-back workflows | Manual | Structured via merge request APIs (better audit trail) |
| Baseline management | Mature | Mature (stream + tracker baselines) |
| API automation potential | Good | Excellent (comprehensive REST API v3) |
| Regulatory compliance support | Good | Strong (electronic signatures, audit trail, review workflows) |
| Test run reuse | Limited | Limited (similar gap) |
| Multi-project streams | Supported | Supported |

---

## Verdict

**The strategy is good — adopt it with the following modifications:**

1. **Transform Streams need a custom automation layer.** This is the biggest delta from the Polarion-native approach. Budget 4–6 weeks of engineering effort for the API-based transformation pipeline, or evaluate the Pure Variants Codebeamer connector if PV is already licensed.

2. **Merge-back is better as a controlled workflow, not automated.** For a regulated medical device environment, the manual merge request gate is actually superior. Lean into Codebeamer's merge request APIs rather than fighting this.

3. **Invest in cross-stream reporting early.** The stream hierarchy will generate enormous traceability data. Build cbQL-based dashboards and review queries before the hierarchy grows beyond 2 tiers.

4. **Establish naming and color conventions before creating the first stream.** With 4 tiers × multiple product lines × multiple releases × market variants, navigability will degrade fast without discipline.

5. **Pilot with one product line end-to-end.** Prove the full 4-tier flow (Library → PL → Transform → Release/Variant) with a single product (e.g., Ingenia or BlueSeal) before rolling out across the portfolio.

---

## Action Items

1. [ ] Validate Pure Variants Codebeamer connector availability and maturity for Transform Stream automation
2. [ ] Design and document the stream naming and color-coding convention
3. [ ] Build a proof-of-concept API-based transformation pipeline for one product line
4. [ ] Define the association type taxonomy for cross-stream traceability
5. [ ] Establish cbQL report templates for cross-stream traceability and test coverage
6. [ ] Pilot the full 4-tier hierarchy with one product line (recommend Ingenia as it has the most variants)
7. [ ] Document the merge-back workflow procedure with regulatory compliance checkpoints
8. [ ] Evaluate performance characteristics with realistic data volumes (target: 10K+ items per stream)
9. [ ] Define supplier collaboration model — permissions, export formats, synchronization cadence

---

*This evaluation is based on Codebeamer API v3.0 (Public and Internal) as available in the project knowledge base, combined with 30+ years of enterprise ALM implementation experience.*
