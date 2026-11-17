# Status

Date: 2026-11-17

The source project has a working 13B workflow planner, DAG executor, A2A client paths, SQLite-backed planning knowledge, demand records, Agent Card observation, and shadow impact diagnostics.

This public repository is a reduced reference extraction. It includes the deterministic parts that can be reviewed without the surrounding private business services:

- demand record structural and source validation
- Agent Card normalization and field-level supply diffs
- conservative dependency-aware impact classification

The following remain deployment work rather than promises of this reference package:

- automatic refresh on every cache lookup
- an enforceable semantic compatibility gate
- automatic targeted replan and active revision promotion
- end-to-end production latency and cost claims
- independent human-labelled accuracy evaluation

Existing local experiments showed that exact plan-cache reuse can reduce repeated planning calls in the source system, but those measurements do not establish the accuracy or end-to-end benefit of the capability-aware incremental mechanism.

The project should be described as an independent implementation and research direction with related prior work in plan caching, workflow dependency tracking, and Agent Card versioning. It should not be described as having no prior art or as a universal first invention.
