# Reference architecture

```mermaid
flowchart LR
    Q[User request] --> D[DemandSignature]
    D --> P[Planner]
    P --> W[Executable DAG]
    W --> E[PlanCacheEntry]
    C[Agent Card] --> S[SupplyObservation]
    S --> X[SupplyDelta]
    E --> I[Impact assessment]
    X --> I
    I --> R{Reuse / review / replan}
    R --> W
```

The design separates demand, observable supply, and plan evidence. Demand describes the user goal independently of the capabilities selected at one point in time. Supply describes the public capabilities exposed by an Agent Card. Plan evidence records the DAG and the exact capability dependencies used to produce it.
