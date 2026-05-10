# Quarantine Records

This folder stores DSCSA events flagged as `QUARANTINE_MISSING_DATA` for manual review.

SOP alignment:
- Sui-Generis SOP Section 8.2

Operational notes:
- Records are written as JSON by `app/services/quarantine.py`.
- A contemporary audit log record is still generated and hash-chained.
- Quarantined records are immutable review artifacts and should not be edited in place.
