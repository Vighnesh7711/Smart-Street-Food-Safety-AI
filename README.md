# Smart Street Food Safety AI

AI-assisted ingredient analysis, hygiene monitoring, multilingual safety guidance, and QR-based transparency for street food vendors and consumers.

## Project Status

Pre-development / planning stage. This repository describes the proposed system before implementation.

Two variants are planned:

- **Software only** — a smartphone or web app for analyzing product labels and stall images. This is the intended MVP.
- **Software + hardware** — adds an ESP32-CAM for automatic periodic stall image capture, to be built after the MVP is validated.

## Problem

Street food vendors often use packaged ingredients without fully understanding ingredient names, additives, or whether a product suits their intended use. Language and technical terminology make labels hard to read. Consumers, in turn, want more transparency about stall hygiene.

This project turns complex product and hygiene information into simple, actionable guidance.

## Who Uses It

**Vendor**
- Registers and enters stall/business details.
- Adds food items and products.
- Scans product labels to understand ingredients and get suitability guidance.
- Runs hygiene checks and views hygiene history.
- Gets a QR code for their stall.

**Consumer**
- Scans a stall's QR code.
- Views permitted hygiene and vendor information.
- Leaves feedback or reports a hygiene concern.

**Authorized Reviewer** (future)
- Reviews reports and records verification outcomes.
- Supports official food-safety workflows without replacing official inspection.

## Core Features

**Product scanning** — Vendor photographs a product label. The image passes a quality check, then goes through OCR to extract ingredient text.

**Explainable results** — The system does not give a plain yes/no. It explains what was detected, what it means, why it might be a concern, and whether an alternative product is available.

**Multilingual support** — English, Marathi, and Hindi at launch, with more Indian languages planned.

**Hygiene monitoring** — Stall images are analyzed for indicators such as working-area cleanliness, visible waste, storage organization, and preparation-area condition. Final indicators will be defined after dataset collection.

**Image coverage validation** — The system checks that submitted images actually cover the required areas (working area, preparation area, storage, waste disposal) rather than accepting a single clean corner.

**QR transparency** — Each stall gets a unique QR code linking to its hygiene information and a feedback/report form.

**Feedback integrity** — Ratings can be manipulated (e.g., a vendor asking many people for 5-star reviews). The system applies rate limiting, duplicate detection, and suspicious-activity checks, and keeps raw feedback separate from verified hygiene status.

**Privacy handling** — Images may contain faces or other sensitive details. Captured images go through detection and blurring of sensitive regions before further processing, and raw image storage is minimized.

## System Architecture

**Software-only version**

Vendor uses their smartphone for both product photos and stall photos. Images go to a backend for OCR/AI processing, results are stored, and a dashboard shows hygiene status behind a QR code for consumers.

Advantages: lower cost, faster to build, no extra hardware.
Limitation: vendor has to manually capture images.

**Software + ESP32-CAM version**

An ESP32-CAM automatically captures stall images on a schedule and sends them over Wi-Fi to the backend, where the same hygiene AI processes them. The ESP32-CAM itself just handles capture, buffering, and upload; heavy AI inference stays on the backend.

Advantages: automatic monitoring, less manual effort.
Limitations: hardware cost, power and Wi-Fi dependency, camera placement, and maintenance.

## AI/ML Components

- **OCR** — converts product label images into text.
- **Ingredient NLP** — extracts and normalizes ingredient names from OCR text.
- **Knowledge-based decision engine** — matches ingredients against defined rules and the intended food application.
- **Computer vision** — detects visible hygiene indicators in stall images.
- **Explainable AI layer** — turns technical analysis into plain-language explanations.
- **Multilingual NLP** — produces explanations in the vendor's preferred language.

Exact models will be selected after experimentation; none are finalized yet.

## Proposed Technology Stack

**Frontend:** React/Next.js, with a native Android app if needed
**Backend:** Python, FastAPI
**Database:** PostgreSQL
**AI/ML:** Python, OpenCV, an OCR engine, PyTorch or TensorFlow, a YOLO-family model for visual detection tasks
**Hardware (optional variant):** ESP32-CAM, Wi-Fi, appropriate power supply, optional local storage

This stack is a starting point and may change during development.

## Database Overview

Planned core entities: `users`, `vendors`, `stalls`, `food_items`, `products`, `ingredients`, `product_ingredients`, `ingredient_rules`, `recommendations`, `hygiene_checks`, `hygiene_indicators`, `hygiene_scores`, `stall_images`, `qr_codes`, `consumer_feedback`, `reports`, `verification_records`, `audit_logs`.

Each vendor owns a stall, which has food items, products (with ingredients), hygiene checks, a QR code, and consumer feedback/reports.

## Repository Structure

```
smart-street-food-safety-ai/
├── README.md
├── docs/
│   ├── architecture/
│   ├── algorithms/
│   ├── database/
│   ├── api/
│   └── research/
├── frontend/
│   ├── web/
│   └── mobile/
├── backend/
│   ├── api/
│   ├── models/
│   ├── services/
│   └── database/
├── ai/
│   ├── ocr/
│   ├── ingredient_analysis/
│   ├── hygiene_detection/
│   ├── explainability/
│   └── multilingual/
├── hardware/
│   └── esp32_cam/
├── datasets/
│   └── README.md
├── tests/
└── scripts/
```

## Development Roadmap

1. **MVP** — Vendor registration, product image capture, OCR, ingredient extraction, knowledge base matching, and multilingual explanation.
2. **Hygiene monitoring** — Stall image validation, computer vision analysis, hygiene scoring.
3. **QR and consumer flow** — QR generation, consumer-facing stall page, feedback and reporting.
4. **Trust and verification** — Fraud detection, report moderation, verification workflow, audit history.
5. **ESP32-CAM integration** — Automatic capture, Wi-Fi upload, backend processing.

The plan is to build the smallest reliable version first, validate it with real data, and add automation and hardware afterward.

## Known Limitations

**Product analysis:** OCR can fail on poor-quality images; ingredient names may have synonyms not yet in the knowledge base; results depend on the intended food application.

**Hygiene AI:** Images cannot capture every hygiene condition; hidden contamination may go undetected; lighting and camera angle affect accuracy; false positives and false negatives are possible.

**Feedback:** Ratings can be manipulated and false reports are possible; community feedback is not a substitute for official inspection.

**Hardware:** Camera placement, Wi-Fi reliability, and power supply all affect the ESP32-CAM variant's monitoring coverage.

No performance numbers should be claimed until testing has actually been carried out.

## Future Scope

Voice-based assistance, additional Indian languages, offline OCR and knowledge base, improved recommendation models, advanced hygiene computer vision, automatic video-based inspection, environmental sensors, integration with official food-safety workflows, randomized verification, stronger feedback-fraud detection, vendor improvement recommendations, historical analytics, and edge AI deployment.

## Project Vision

The project connects two goals:

- Turning complicated ingredient information into a simple explanation the vendor can act on.
- Turning stall conditions into a hygiene indicator that a consumer can see through a QR code.

The aim is to make food safety information understandable and actionable for vendors, while giving consumers real transparency.
