# Fieldkit Document Intelligence Service (`fieldkit-docai`)

Project 4: Contract and Document Intelligence Engine for Halden Industrie GmbH.

## Features
- Ingestion with magic-byte validation and SHA-256 deduplication
- Page preprocessing (200 DPI rendering, OpenCV deskewing, noise reduction)
- OCR with text layer detection and Tesseract deu+eng fallback
- Resumable pipeline steps with `document_step` audit tracking
- Delivery note parsing with Donut and deterministic business validators
- Contract clause extraction, CUAD multi-label classification, and playbook risk evaluation
