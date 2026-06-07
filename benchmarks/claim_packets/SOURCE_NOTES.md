# Benchmark Document Source Notes

The first benchmark packet in `auto_claim_v1/` is synthetic text authored for local tests. It intentionally contains no real claimant, medical, financial, or accident data.

Use these public sources only as layout/category references for future fixtures. Prefer blank public forms plus synthetic values. Do not import filled claim packets or public search results that may contain PII/PHI.

| Source | Useful For | Source Type | Caveat |
| --- | --- | --- | --- |
| https://www.cms.gov/medicare/forms-notices/cms-forms/cms-forms-items/cms1188854 | CMS-1500 health insurance claim form | Public blank federal form | Blank form only; verify current OMB/revision before production-like benchmarks. |
| https://www.cms.gov/medicare/coverage/summary-notice | Medicare Summary Notice samples | Public CMS sample notices | Good EOB-style examples; not representative of every private payer. |
| https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files | Synthetic Medicare claims data | Synthetic public use data | Data files, not document images; read CMS usage notes. |
| https://synthetichealth.github.io/synthea/ | Synthetic medical records | Synthetic generated data | Useful for medical evidence content; not native insurer forms. |
| https://www.wcb.ny.gov/content/main/forms/Forms_EMPLOYER.jsp | Workers compensation forms | Public blank state forms | Use current versions; some forms require Acrobat. |
| https://www.tdi.texas.gov/forms/form20.html | Texas DWC workers compensation forms | Public blank state forms | Operational alternate forms may require approval. |
| https://www.osha.gov/recordkeeping/forms | OSHA 300/300A/301 injury reports | Public blank federal forms | Good workplace incident report reference; keep synthetic values. |
| https://www.dmv.ca.gov/portal/vehicle-registration/report-of-traffic-accident-occurring-in-california-sr-1/ | California SR-1 accident report | Public blank state form | Use only with synthetic data. |
| https://dmv.ny.gov/forms/mv104.pdf | New York MV-104 accident report | Public blank state form | Direct PDF; use only with synthetic data. |
| https://www.fema.gov/flood-insurance | FEMA/NFIP property claim references | Public government source | FEMA form URLs move; verify current proof-of-loss material. |

Fixture rule: every benchmark packet should include a `manifest.json`, text documents, expected document classes, expected fields, and a short note if it was derived from a public blank form.
