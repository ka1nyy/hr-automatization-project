# Recruitment and hiring

Recruitment selects an accepted candidate; formal hiring is a separate transactional case.

```mermaid
stateDiagram-v2
    [*] --> Request
    Request --> HRReview
    HRReview --> Request: return
    HRReview --> Rejected: reject
    HRReview --> StaffingReview: approve
    StaffingReview --> Request: return
    StaffingReview --> Vacancy: approve vacant capacity
    Vacancy --> Application: publish and receive consented candidate
    Application --> Rejected: screening reject
    Application --> Interview: advance
    Interview --> Commission
    Commission --> Offer: quorum recommendation
    Offer --> Closed: decline
    Offer --> Hiring: accept
    Hiring --> Hired: documents/tasks complete
    Hiring --> Cancelled: cancel with reason
```

The request and hiring assignment use authoritative organization, unit, position, published
structure and staffing-slot capacity. Evaluations are immutable per evaluator; commission decisions
require configured quorum/conflict declarations. Completion locks capacity, prevents duplicate
employee numbers and atomically creates Person, Employee and primary Assignment, then fills the
vacancy. Incomplete mandatory checklist/onboarding work blocks completion.

Email, phone and identity data are encrypted at rest and redacted from generic output, audit and
outbox. Consent is mandatory. Expired records may be anonymized only without active applications.
External publication is explicitly recorded as manual until a job-board adapter exists.

Creating a recruitment request or hiring case starts the published workflow version in the same
database transaction and stores its instance ID on the business record. Returned requests may be
corrected and resubmitted only by the original requesting employee and only in the original unit.
Interview evaluations bind the authenticated account to the configured participant employee;
commission members, protocol documents, publication owners, and checklist records are checked
against the authoritative organization.
