# OCR Provider And Cost Strategy

Date: 2026-06-06

## Verdict

Do not make Azure the only OCR path.

Use a **hybrid provider router**:

1. Use free/local extraction first when possible.
2. Use low-cost parsing for development and early demos.
3. Use Azure/AWS/Google only when quality, compliance, or customer requirements justify it.
4. Cache every OCR result by file checksum so the same document is never billed twice.
5. Benchmark providers on real claim packets before committing to one.

The product strategy is to provide a full solution with cheap operating expenses. That means our differentiation cannot be "we call expensive OCR APIs on every page." The system must route pages intelligently.

## Recommended Provider Strategy

### Development Default

Use:

- Mock OCR.
- Local PDF text extraction for digital PDFs.
- Recorded OCR fixtures.
- Optional open-source OCR for experiments.

Cost: near `$0`.

No normal unit test, frontend test, or orchestrator smoke test should call a paid OCR provider.

### MVP / Demo Default

Use:

- Local PDF text extraction when the PDF already has embedded text.
- Open-source OCR for simple scanned pages.
- Optional low-cost parser for harder documents.
- Paid cloud OCR only for selected pages.

Goal: keep development and demos cheap while still supporting real uploaded documents.

### Pilot Default

Benchmark at least two providers side by side:

- Azure Document Intelligence as the enterprise/compliance baseline.
- LlamaParse or equivalent document parser as a low-friction parser baseline.
- PaddleOCR / PaddleOCR-VL / Surya as self-hosted cost-control candidates.
- AWS Textract and Google Document AI as fallback baselines.

Do not choose the final production provider until we measure actual claim packet results.

## Why Azure Alone Is Not Enough

Azure Document Intelligence is strong for enterprise pilots:

- OCR/layout.
- Tables.
- Forms.
- Prebuilt models.
- Custom models.
- Microsoft enterprise trust.
- Possible private/container options.

But Azure is not automatically cheapest. Cloud OCR pricing is page-based, and structured extraction can become expensive at scale.

Azure should be our **enterprise cloud baseline**, not the default path for every document page.

## Cost Trap

The expensive part is not basic OCR. The expensive part is running advanced document extraction on every page.

AWS Textract pricing illustrates the shape of the problem:

- Basic text detection can be low-cost per page.
- Forms/key-value extraction costs much more.
- Tables add more cost.
- Forms + tables + queries at high volume can become very expensive.
- Specialized document packages can be useful but expensive.

So the winning strategy is:

```text
classify first
  -> route cheap pages cheaply
  -> send only hard/valuable pages to expensive extraction
  -> cache results
  -> escalate low-confidence pages to stronger provider or human review
```

## Provider Comparison

| Provider | Cost Fit | Quality Fit | Compliance Fit | Best Use |
| --- | --- | --- | --- | --- |
| Mock OCR | Free | Fake/deterministic | Local only | Tests and development |
| PDF text extraction | Free | Great for digital PDFs | Local | First pass before OCR |
| Tesseract | Very cheap | Weak on messy claims docs | Self-hosted | Simple OCR fallback |
| PaddleOCR / PaddleOCR-VL | Cheap infra-only | Promising, needs benchmark | Self-hosted | Cost-reduction path |
| Surya OCR | Cheap infra-only | Strong modern OCR/layout candidate | Self-hosted | Benchmark candidate |
| LlamaParse | Low/medium | Strong AI-ready parsing | SaaS/hybrid options | Fast MVP parsing |
| Azure Document Intelligence | Medium | Strong layout/forms/tables | Strong enterprise fit | Pilot baseline |
| Google Document AI | Medium/high | Strong document processors | Strong enterprise fit | Fallback benchmark |
| AWS Textract | Medium/high | Strong OCR/forms/tables/queries | Strong enterprise fit | AWS-customer fallback |
| ABBYY | High | Strong enterprise IDP | Strong enterprise/on-prem | Enterprise fallback, not startup default |

## Recommended Router

Use provider routing instead of one hardcoded model.

```text
Uploaded PDF/image
  -> hash file/page
  -> check OCR cache
  -> if digital text exists: use local text extraction
  -> if simple scan: use open-source OCR
  -> if table/form/checkbox/signature-heavy: use cloud layout provider
  -> if low confidence: escalate to stronger provider or human review
  -> store OCR artifacts and provider metadata
```

## Cost Controls To Build Into The System

1. `NEURODOCOPS_OCR_PROVIDER=mock|local|azure|aws|google|llamaparse|paddle`
2. Paid providers disabled by default.
3. `NEURODOCOPS_LIVE_OCR_ENABLED=false` by default.
4. OCR cache keyed by file checksum and provider settings.
5. Page-level cache for large packets.
6. Do not reprocess unchanged documents.
7. Store provider/model/version/page count/cost estimate.
8. Log every paid OCR request.
9. Add monthly/page budget warnings.
10. Skip live OCR tests unless provider credentials are explicitly set.

## What We Should Benchmark

Use 20-50 complete claim packets or 100-300 representative pages.

Include:

- Clean digital PDFs.
- Bad scans/faxes.
- Claim forms.
- Incident reports.
- Repair invoices.
- Medical bills.
- EOBs.
- Identity evidence.
- Insurance cards.
- Letters/correspondence.
- Checkbox/signature pages.
- Mixed packets needing split/classification.

Score:

- OCR word accuracy.
- Document classification accuracy.
- Table reconstruction quality.
- Required-field precision/recall.
- Citation correctness.
- Page/region traceability.
- Latency.
- Cost per packet.
- Human correction time.
- Reviewer trust.

The best provider is not the one with the best OCR benchmark only. It is the one with the lowest **cost per accepted reviewed packet**.

## Fit-Test Before Plugging A Provider

Do not integrate OCR providers because they are famous. Integrate them only after they pass a NeuroDocOps fit test.

Fit-test flow:

```text
provider candidate
  -> research pricing/features/compliance
  -> run on benchmark packet set or recorded fixture
  -> normalize output into NeuroDocOps OCR/citation artifacts
  -> score quality, cost, latency, compliance, and reviewer value
  -> decide provider tier and document-type routing
```

Provider decision outcomes:

- Reject.
- Keep as experimental.
- Cheap-tier provider.
- Balanced-tier provider.
- Premium provider.
- Enterprise/customer-specific provider.
- Use only for specific document types, such as invoices, tables, ID cards, or bad scans.

OCR-specific scorecard:

| Area | Required Question |
| --- | --- |
| Text | Does it read claim packet pages accurately? |
| Layout | Does it preserve reading order, sections, tables, checkboxes, signatures? |
| Citations | Can a reviewer verify source page/snippet/region? |
| Tables | Does it handle invoices, medical bills, and EOB rows correctly? |
| Cost | What is cost per page and per accepted packet? |
| Latency | Is it fast enough for reviewer workflow? |
| Failure | What happens on empty output, timeout, bad scan, or provider outage? |
| Compliance | Does it fit customer PHI/PII/cloud requirements? |
| Integration | How hard is artifact normalization and maintenance? |

Rule:

> No OCR provider becomes the default until it wins a fit test for our target claim packet workflow.

## Practical Choice

### If We Need Cheapest Development

Use:

```text
mock OCR + local PDF text extraction + open-source OCR experiments
```

### If We Need Fast Demo With Real Documents

Use:

```text
local extraction first + LlamaParse/Azure only for hard pages
```

### If We Need Regulated Enterprise Pilot

Use:

```text
Azure Document Intelligence as baseline + cache + selective routing
```

### If We Need Lowest Production Cost

Use:

```text
self-hosted PaddleOCR/Surya for easy pages + cloud OCR only for difficult pages
```

## Engineering Impact

This should not affect the whole system if we keep provider boundaries.

Add providers behind:

```text
OCRProvider
ExtractionProvider
```

The workflow should not care whether OCR came from Azure, AWS, Google, LlamaParse, PaddleOCR, or mock.

The worker should choose the provider from config and route per document/page.

## Final Recommendation

Do not blindly use Azure for everything.

Use Azure as the enterprise baseline and compliance-friendly pilot option.

Use mock/local/open-source paths to keep development cheap.

Build a router and cache before live provider usage grows.

The strategy should be:

> Cheap by default, cloud-quality when needed, benchmark-driven before commitment.

## Sources

- Azure Document Intelligence pricing page: supports free tier, pay-as-you-go, layout, prebuilt, custom classification/extraction, containers, and commitment tiers.
- Google Document AI pricing page: provider pricing and processor costs vary by processor/use case.
- AWS Textract pricing page: shows low-cost basic text detection but significantly higher costs for forms, tables, queries, ID, expense, and lending extraction features.
- OCR audit agent research comparing Azure, Google, AWS, ABBYY, LlamaParse, PaddleOCR, Tesseract, docTR, Surya OCR, and EasyOCR for claims packet use cases.
