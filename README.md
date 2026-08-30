# Smart Street Food Safety AI

AI-based ingredient analysis, explainable food-safety guidance, and vendor hygiene monitoring for street food vendors and consumers. Software-only web/mobile platform.

## Project Status

Project report stage, August 2026. This is a software-only system. There is no hardware component in this design.

## Abstract

Street food vendors and consumers often find it difficult to understand ingredient labels, food-safety practices, and hygiene information. This platform lets a vendor create a stall profile, photograph a packaged product's label, and receive an explainable, risk-oriented recommendation in their preferred language, generated from a curated food-safety knowledge base rather than a plain safe/unsafe guess.

A second module lets vendors record hygiene conditions through a checklist and periodic stall photographs. Computer vision is used only as supporting visual evidence, not as proof of microbiological safety. A hygiene score is calculated from checklist compliance, visual evidence, verified inspections, and moderated consumer feedback.

Every registered stall gets a QR code. Consumers scan it to see the stall's public hygiene profile and can submit feedback or report a concern, which an authorized food-safety or municipal officer can review and verify.

The system is an assistive decision-support platform. It does not replace statutory food inspection or laboratory testing.

## Problem Statement

Street food vendors may use packaged ingredients without understanding their composition, additives, allergen information, or suitability for a specific dish. Consumers have limited visibility into a stall's hygiene practices. Official inspection systems are important but do not give every vendor continuous, simple, multilingual guidance.

The system needs to:

- Read and interpret packaged-food ingredient labels from photographs.
- Provide evidence-based, explainable guidance in the vendor's preferred language.
- Recommend alternatives when a verified alternative exists.
- Help vendors record periodic hygiene conditions.
- Generate a transparent, non-authoritative hygiene score.
- Expose verified information through a stall-specific QR code.
- Let consumers submit feedback and reports.
- Help authorities prioritize cases that need verification.

## Out of Scope

- Laboratory testing of food samples.
- Certifying a product as legally safe from an image alone.
- Replacing FSSAI, municipal, or other statutory inspections.
- Detecting microorganisms from ordinary photographs.
- Medical or nutritional diagnosis.

## User Roles

**Vendor** — Registers the stall, records food items and products, scans labels, completes hygiene checks, and receives guidance.

**Consumer** — Scans the stall's QR code, views the public profile, gives feedback, and reports concerns.

**Authority** — Reviews flagged cases, performs verification, and records official observations.

**Administrator** — Maintains the system, the food-safety knowledge base, supported languages, users, and audit logs.

## Core Modules

1. Authentication and role management
2. Vendor/stall profile management
3. Food-category and product management
4. Product label capture and OCR
5. Ingredient extraction and normalization
6. Food-safety rule/knowledge-base engine
7. Explainable recommendation engine
8. Multilingual translation layer
9. Hygiene checklist
10. Stall image quality and visual hygiene analysis
11. Hygiene scoring engine
12. QR code generation and public stall profile
13. Consumer feedback and reporting
14. Authority verification workflow
15. Notifications and audit logs

## How Product Analysis Works

The vendor photographs the back of a packaged product. The system checks image quality, runs OCR, extracts the ingredient list, normalizes the ingredient names, and compares them against the verified knowledge base.

Rather than a plain "unsafe" label, the decision engine returns one of three categories:

- **Verified concern** — an authoritative rule explicitly flags the ingredient or product for the defined use case.
- **Needs review** — OCR is uncertain, the ingredient is ambiguous, or the knowledge base lacks sufficient evidence.
- **No flagged concern** — no rule in the configured knowledge base is triggered.

This keeps the system from presenting an uncertain AI prediction as a legal or scientific fact.

## How Hygiene Monitoring Works

**Self-check** — The vendor completes a short checklist in their selected language, covering working-surface cleanliness, food covering, separation of raw and ready-to-eat items, waste management, utensil cleanliness, hand hygiene, ingredient storage, and water/ice handling.

**Image verification** — The vendor uploads photographs of the preparation area, storage area, waste area, and serving/display area. An image-quality check rejects photos that are too close, dark, blurred, or narrowly framed, and asks for another image.

**Visual hygiene AI** — A lightweight object detector looks for visible evidence such as uncovered food, visible waste, cleaning equipment, or cluttered surfaces. This is treated as supporting evidence only, never as proof of microbiological cleanliness.

**Hygiene score** — Calculated as:

```
H = wc·C + wv·V + wf·F + wa·A
```

Where C is checklist compliance, V is visual-evidence score, F is moderated consumer feedback, A is authority verification, and the weights (wc, wv, wf, wa) are configurable and documented, so that a large volume of reviews cannot override verified inspection evidence.

**Adaptive check interval** — The self-check frequency depends on risk level, recent verified status, and report activity, not on the vendor directly. A low-risk vendor with consistent verified evidence may get a longer interval; a recently flagged vendor gets a shorter one.

## QR-Based Transparency

Each stall gets a unique QR code. Its public profile shows only information meant to be public — no personal contact details, private photographs, or internal authority notes.

## Consumer Feedback Integrity

To reduce coordinated or fake reviews, the system considers account age, repeated reviews from the same account or device, abnormal review bursts, verified QR scans, reviewer diversity, similarity between review texts, and authority verification. No single factor proves fraud on its own — suspicious activity is flagged for moderation rather than acted on automatically.

## Core Algorithms

1. **OCR and ingredient extraction** — capture, orientation/perspective correction, denoise and contrast improvement, OCR, ingredient-section detection, normalization, and confidence scoring; uncertain tokens go to manual confirmation.
2. **Ingredient knowledge-base matching** — each normalized ingredient is matched against rules specifying category, applicable use, concern type, evidence source, recommended action, alternative, and multilingual explanation.
3. **Explainable recommendation** — retrieves matching rules, ranks them by authority and relevance, generates a structured decision with evidence and confidence, then translates the explanation. A generative model, if used, may only paraphrase retrieved evidence — never invent regulatory claims.
4. **Image quality and framing check** — scores scene coverage, blur, illumination/contrast, and framing completeness; below a threshold, the system requests another image.
5. **Consumer feedback trust score** — evaluates the factors listed above to flag suspicious feedback patterns for moderation.

## AI/ML Components

| Component | Purpose |
|---|---|
| OCR | Extract text from ingredient labels |
| OpenCV | Crop, denoise, threshold, correct perspective, check image quality |
| YOLO (optional) | Detect visible hygiene-related conditions in stall photos |
| Rule engine | Make grounded ingredient and hygiene decisions |
| NLP/NER | Identify ingredient names and label entities |
| Translation model/API | Convert verified explanations into the vendor's language |
| LLM (optional) | Produce explanations strictly grounded in retrieved evidence |

A rule engine is used for safety decisions rather than a purely learned classifier, because a learned model can produce plausible but unsupported predictions, and food-safety guidance needs to be traceable. The pipeline separates AI perception from verified knowledge and explanation, rather than going straight from image to answer.

## System Architecture

1. **Presentation layer** — React.js/Next.js responsive web app or PWA.
2. **Application layer** — FastAPI/Node.js APIs, authentication, vendor workflows, reporting, score calculation.
3. **AI layer** — OpenCV preprocessing, OCR, ingredient extraction, computer vision, grounded explanation.
4. **Knowledge layer** — curated ingredient rules, product categories, regulatory references, alternatives, multilingual explanations.
5. **Data layer** — PostgreSQL for structured data, object storage for images.
6. **Authority layer** — moderation and verification dashboard.

## Technology Stack

- **Frontend:** React.js / Next.js, responsive PWA
- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL
- **Object storage:** S3-compatible or cloud object storage
- **OCR:** PaddleOCR or Tesseract
- **Image processing:** OpenCV
- **Computer vision:** YOLO-family model on a limited custom hygiene dataset
- **Authentication:** JWT/session-based, role-based access control
- **QR generation:** standard QR-code library
- **Deployment:** Docker and a cloud platform

## Database Overview

Main entities: `users`, `stalls`, `foods`, `products`, `ingredients`, `rules`, `alternatives`, `hygiene_checks`, `hygiene_images`, `feedback`, `reports`, `verifications`, `audit_logs`.

## Requirements Summary

**Functional** — vendor registration and stall profile, food category and product management, label capture with image-quality validation, OCR extraction, ingredient normalization and knowledge-base matching, recommendation and explanation generation in the selected language, hygiene checklist and scoring with visible component breakdown, unique QR code per stall, public stall profile for consumers, feedback and reporting, authority review and verification, and an audit history for score and verification changes.

**Non-functional** — simple, local-language usability; interactive-time performance for OCR and recommendations; authenticated and encrypted access; privacy-conscious handling of images (blurring faces where feasible); every recommendation traceable to a rule or evidence source; retryable uploads; independently extensible rules, languages, and locations; auditability of important changes.

## Repository Structure

```
street-food-safety/
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── features/
│       │   ├── vendor/
│       │   ├── consumer/
│       │   ├── authority/
│       │   ├── product-scan/
│       │   └── hygiene/
│       ├── services/
│       ├── hooks/
│       └── i18n/
├── backend/
│   └── app/
│       ├── api/
│       ├── models/
│       ├── schemas/
│       ├── services/
│       │   ├── ocr/
│       │   ├── vision/
│       │   ├── rules/
│       │   ├── explanation/
│       │   ├── translation/
│       │   └── scoring/
│       ├── database/
│       ├── security/
│       └── workers/
├── ai/
│   ├── ocr/
│   ├── ingredient_ner/
│   ├── hygiene_detection/
│   └── datasets/
├── training/
├── knowledge_base/
│   ├── ingredients/
│   ├── rules/
│   ├── alternatives/
│   └── translations/
├── tests/
├── docker/
└── docs/
```

## Testing Plan

Testing proceeds module by module before the full workflow: authentication, OCR, ingredient extraction, rule matching, explanation generation, translation, image quality, hygiene detection, hygiene scoring, QR retrieval, feedback moderation, authority workflow, and finally end-to-end validation. Metrics include accuracy, precision/recall, mAP for visual detection, latency, and audit completeness. No performance numbers are claimed until testing is actually carried out.

## Security, Privacy, and Ethical Considerations

- Images with faces are detected and blurred before cloud processing where practical.
- Only information necessary for the stated purpose is collected.
- Vendor location is public only to the precision the use case requires.
- Consumer identity is not unnecessarily exposed to vendors.
- Important changes to hygiene scores and verification status are auditable.
- Reports do not immediately reduce a vendor's score without a trust/moderation step.
- Coordinated reviews are flagged, not automatically treated as fact.
- AI recommendations clearly state when evidence is insufficient.
- The system distinguishes an "AI-assisted advisory result" from an "official inspection result."

## Known Limitations

- OCR can fail due to glare, curved packaging, low resolution, stylized fonts, or multilingual labels, and can produce incorrect ingredient names.
- The knowledge base may not cover every ingredient or product formulation, and stored product information needs updating as formulations change.
- Visual hygiene detection is limited to what's visible in a photo and cannot prove microbiological safety.
- Consumer feedback can be manipulated.
- QR codes can be copied unless tied to a verifiable stall identity.
- Multilingual translation can introduce ambiguity if not validated.
- The system cannot replace statutory food-safety inspections or laboratory testing.

## Future Scope

- Integration with official food-business registration and verification systems where permitted.
- Integration of authoritative food-product and regulatory databases.
- Barcode/QR product lookup before OCR.
- Offline OCR and multilingual assistance for low-connectivity areas.
- Voice-based guidance for vendors with limited literacy.
- More Indian languages and regional dialect support.
- Automatic change detection between consecutive stall photographs.
- Privacy-preserving or federated learning for hygiene models.
- Authority mobile application for inspection and verification.
- Predictive risk prioritization for authorities.
- Integration with certified training resources for food handlers.

## Conclusion

The Smart Street Food Safety and Hygiene Assistant is a practical software platform for improving day-to-day food-safety awareness among street food vendors while increasing transparency for consumers. It combines ingredient-label OCR, a verified knowledge base, explainable multilingual guidance, hygiene self-checks, visual evidence, QR-based public profiles, moderated consumer feedback, and authority verification into one workflow. It is deliberately an assistive platform: AI reduces the knowledge and language barrier, it does not replace scientific testing or statutory inspection.

## References

1. Food Safety and Standards Authority of India (FSSAI), Hygiene Rating Scheme.
2. FSSAI, Clean Street Food Hub, Eat Right India initiative.
3. FSSAI, Food Safety and Standards (Labelling and Display) Regulations, 2020.
4. Pushkar, K., Bhatt, G., Verma, M., Goel, S., Singh, A., "Conformance of the food vendor carts design to the prescribed standards as per food safety and standards regulations: Assessment from an urban area of North India," Indian Journal of Public Health, 2022.
5. Redmon, J., Divvala, S., Girshick, R., Farhadi, A., "You Only Look Once: Unified, Real-Time Object Detection," CVPR.
6. Smith, R., "An Overview of the Tesseract OCR Engine," ICDAR.
