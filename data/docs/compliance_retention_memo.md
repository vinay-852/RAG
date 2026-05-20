# Compliance Retention Memo

Audit records for privileged access, vendor onboarding, data exports, and policy
exceptions must be retained for seven years. Records are immutable and appended to
the audit event store. Corrections require a new audit event that references the
original object identifier.

Compliance reviewers may inspect before and after values for access-policy changes.
General employees may read public retention rules but cannot inspect detailed audit
payloads.
