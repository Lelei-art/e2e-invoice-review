# Sample invoices

The project includes 12 fictional invoices and one Dutch fuel receipt in English, Dutch, German, and French. `manifest.json` records the expected document type, normalized fields, and policy outcomes. No private document or random internet scrape belongs in this repository.

All committed samples are already generated. Run the offline policy check against the expected manifest outcomes:

```powershell
uv run --project backend --locked --no-sync python backend/scripts/evaluate_corpus.py
```

This verifies deterministic issue codes and duplicate behavior without Azure. The optional live evaluator (`--live`) can make up to 52 provider requests for 13 documents and may incur charges. See [the API and pipeline guide](../docs/api-and-pipeline.md#checking-the-evaluation-manifest) for details.

To inspect a sample with Document Intelligence, run the corresponding playground command from the repository root:

```bash
uv run --project backend --locked --no-sync python -m playground.map_document --type invoice samples/generated/01-en-happy-classic.pdf
uv run --project backend --locked --no-sync python -m playground.map_document --type receipt samples/generated/13-nl-fuel-receipt.png
```

Each mapping command sends one document to Azure and may incur usage charges.

The committed set contains eleven PDFs and two PNG images. VAT values are fictional checksum examples and are never presented as verified business registrations.

Microsoft's official sample invoice is downloaded locally for the first Azure provider check and ignored by Git:

```bash
curl -L \
  https://raw.githubusercontent.com/Azure-Samples/cognitive-services-REST-api-samples/master/curl/form-recognizer/sample-invoice.pdf \
  -o samples/sample-invoice.pdf
```

Optional external research datasets:

- [FATURA](https://zenodo.org/records/8261508): 10,000 synthetic English invoices across 50 layouts, CC BY 4.0.
- [DocILE](https://docile.rossum.ai/): annotated and synthetic business documents with research access.
- [CORD](https://github.com/clovaai/cord): Indonesian receipts, useful for expanding receipt evaluation.
- [SROIE](https://arxiv.org/abs/2103.10213): scanned receipt OCR benchmark.
