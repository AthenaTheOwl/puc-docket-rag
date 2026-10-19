# Citation membership and claim support are separate checks

Method update: October 18, 2026. Proposed experiments below are not reported as executed results.

The extraction gate drops a rule whose chunk id was not retrieved. That establishes citation membership. A retrieved paragraph may still oppose the extracted rule, describe a proposal, apply to another customer class, or quote a party rather than a commission finding.

Proposed synthetic acceptance cases:

| Passage | Extracted claim | Required review |
|---|---|---|
| A party proposes allocating cost to residential customers | The commission adopted that allocation | Reject the status mismatch |
| The order rejects the proposed charge | The order approves the charge | Reject the polarity reversal |
| The rule applies only to new large-load contracts | The rule applies to every customer | Reject the scope expansion |

Preserve document version, docket, page/line anchor, speaker and procedural status. Evaluate retrieval recall and extraction support separately. A future docket amendment should queue the dependent rule and downstream ratepayer assumption for review without deleting the historical extraction. These checks are proposed; the current membership gate remains the implemented boundary.

## References

- https://github.com/3orionkings/ai-product-team/blob/main/workflows/process-change.md
- https://www.ferc.gov/explainer-interconnection-final-rule
