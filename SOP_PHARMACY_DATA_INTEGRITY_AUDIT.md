# SOP: Pharmacy Data Integrity Audit

Objective: Rapid conversion of independent pharmacy owners to paid audit clients.
Persona: Lead Systems Engineer (Sui-Generis LLC).

## 1) The Contact (Incident Response)
Target: Pharmacist-in-Charge (PIC) or Owner

Opening Gambit:
"I am Andrew with Sui-Generis. I am a systems engineer specializing in DSCSA 2026 data integrity. I am performing local stress tests on serialization logs because many vendors are currently passing data that fails ALCOA+ standards."

Sui Generis Differentiator:
- Do not say: "I have software to sell you."
- Do say: "I have a mobile-first engineering lab (Termux/Sentinel) that audits your vendor's EPCIS strings in real time."

## 2) The Demo (The Visual Hook)
Action: Open DSCSA_Audit_Pitch.md in Markor Preview Mode.

Demo Sequence:
1. Point to ALCOA+ section:
   Explain that "Accurate" and "Contemporaneous" are the two biggest failure points.
2. Explain the Ghost Data threat:
   If a manufacturer recalls a serial number and the Transaction Statement was not logged correctly, the full bottle value may be lost.
3. Show the failure table:
   "This is what a format mismatch looks like. Your scanner may beep green, but the FDA-facing flow sees red."

## 3) The Closing (Fast Income)
Goal: $500 for a Baseline Integrity Report.

The Ask:
"I do not want to replace your system. I want to audit it. For $500, I will run a 1,000-line log audit with the Sentinel framework. You get a Gap Analysis you can send to your vendor so they can fix your data before the 2026 deadline. If I find zero errors, the audit is on me."

Operator Note:
- Keep this as an audit-first engagement, not a platform replacement pitch.
- Focus on regulatory and financial risk reduction.

## Study Key: Terms To Drop
- EPCIS: Electronic Product Code Information Services (the language of the scan)
- GS1-128: Barcode standard
- 21 CFR Part 11: Regulation for electronic records and signatures
- VRS: Verification Router Service (the manufacturer verification call path)

## Field Checklist
- Confirm decision-maker role (PIC or Owner)
- Deliver opening gambit in under 20 seconds
- Run visual demo in Markor
- Show at least one clear FAIL example
- Present fixed-price offer ($500 baseline audit)
- Schedule follow-up for report delivery

## Evidence Outputs to Offer
- Baseline Integrity Report (summary)
- Gap Analysis (vendor-facing)
- Quarantine Exceptions list
- Hash-chain integrity verification output

## End of SOP
