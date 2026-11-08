# Data privacy and security note

Design principle: treat the synthetic pack as real customer data. Collect the minimum, say why, keep it briefly, and make the owner's choices visible.

## What we collect, and why (purpose limitation)

| Data | Why | When |
|---|---|---|
| Business type, city, staff, sites, current internet, GST/Udyam status | Recommend a bundle that is eligible for them | Advisor chat |
| GST certificate, Udyam certificate, signatory ID, address proof | Verify the business and signatory, activate service | Only after explicit consent |
| Typed name | E-signature on the order | Checkout |

We do not collect Aadhaar numbers, bank details or photos. The advisor never asks for an ID number in chat; identifiers are only read from documents the owner chooses to upload.

## Consent (DPDP Act, 2023)

- A consent screen appears **before any document is requested**. It states the purpose, what is collected, retention, and the right to withdraw or erase. It is shown in the owner's language.
- The server refuses document uploads (`403`) until consent is recorded. Each consent is stored with timestamp, version (`2026-07-v1`), language and purposes.
- Declining keeps the owner in the journey (they can go back and talk to a partner). Withdrawing consent deletes everything extracted so far.

## Data minimisation and retention

- **Document images are never stored.** They are decoded in memory, read by local OCR, and discarded in the same request. Only the extracted fields are kept.
- Extracted fields are kept **90 days after activation**, or **30 days** if the owner does not go ahead (`RETENTION_DAYS_*` in `backend/app/config.py`). A purge job is the next step; the policy is already exposed at `GET /api/kyc/policy`.
- Chat: only the structured profile is saved, not the raw conversation.

## Masking

- Identifiers in logs and the audit table are masked (`37*******7ZS`). The UI shows masked GSTINs after verification; the full number appears only when the owner is asked to confirm a correction.
- The registry lookup APIs return only what the owner needs to confirm their own details.

## Local AI: nothing leaves the machine

- The advisor model (Gemma 3 4B), OCR (RapidOCR) and the lead-scoring model all run locally. No document, chat text or identifier is sent to a third-party AI service. This is a deliberate privacy choice, not only a cost choice.
- LLM output is never trusted for decisions: eligibility, price and KYC verdicts come from deterministic code. An explanation that mentions a price or product outside the bundle is discarded and replaced by a template.

## Security choices

- Uploads: images only, 8 MB limit, parsed in memory.
- No PII in URLs; sessions use random 12-character IDs.
- KYC outcomes include a **human review path** (manual review and blocked cases go to the sales/partner queue) so a wrong automatic decision is never final.
- Audit log records consent, lookups, KYC verdicts and orders, with masked identifiers.

## Known gaps (honest list)

- No authentication on the back-office view. Production needs SSO and role-based access, with partners seeing only their own leads.
- No encryption at rest for the SQLite file. Production should use an encrypted database and field-level encryption for extracted KYC fields.
- Retention purge is specified but not scheduled.
- Machine-translated consent text (non-Hindi, non-English) must be reviewed by a native speaker and legal before launch.
- Blur threshold and skew correction are tuned on specimens; real phone photos need calibration.
