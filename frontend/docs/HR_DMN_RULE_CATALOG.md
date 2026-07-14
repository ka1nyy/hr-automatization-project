# HR DMN rule catalog

| Decision | Inputs | Output | Status |
| --- | --- | --- | --- |
| Leave eligibility | Employee status, requested days, balance | Eligible or rejection code | Implemented as repository validation; DMN deferred |
| Probation completion | Review score, required tasks | Complete or extend | Deferred |
| Candidate screening | Vacancy criteria, candidate attributes | Screening result | Deferred |

The leave rule currently rejects non-positive periods and requests above balance. When the decision gateway is available, the HTTP repository should return the same stable domain errors.
