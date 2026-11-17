# Data model

## DemandSignature

A source-grounded record of goals, constraints, required context, and explicit ordering. Evidence strings must be traceable to the current request. A reused plan must never copy the previous request's demand record into a new request.

## SupplyObservation

A normalized Agent Card snapshot. The reference keeps stable business fields, Skill identifiers, input/output modes, and contract extensions. It excludes credentials, request headers, and private execution data.

## PlanCacheEntry

A versioned record containing the original request, current demand signature, executable DAG, selected capability and Skill dependencies, contract fingerprints, supply snapshots, planner/schema versions, revision, and status. It does not contain the last answer or business result.
