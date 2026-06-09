# PLAN.md — Contact Finder Challenge

## Architecture

**System Flow**: CSV (company_name, address) → Multi-source enrichment (parallel queries to registry, listing, enrichment API) → Signal fusion & classification → Output formatter → CSV/JSON with contact + confidence + provenance

**Components**: Query controller → Enrichment fetcher (3 parallel calls) → Conflict resolver → Confidence scorer → Output serializer

**Key Principles**: 
1. Multi-source redundancy — combine independent signals; no single source suffices
2. Parallel fetching — query all sources concurrently to minimize latency
3. Provenance-first — every field traceable to source_url
4. Precision over recall — honest "cannot verify" beats wrong contact
5. Transparency — explainable confidence scores

---

## Sources & Strategy

**Three Data Sources** (independently fallible):

| Source | Strength | Weakness |
|--------|----------|----------|
| **Registry** | Legal ownership record; authoritative for owner/founder | Slow to update; incomplete for small biz; no contact method |
| **Listing** | Up-to-date phone/info; recent updates | Generic main line; no individual named; may be stale |
| **Enrichment** | Email/phone linked to domain; fast lookup | Weak signals; self-reported confidence unreliable; may hallucinate |

**Why This Mix**: No single source is complete. Agreement across sources = high confidence. Single weak source = low confidence.

**How They Fail**: Registry stale (ownership transferred), listing generic (main line), enrichment hallucinates (plausible but unverifiable).
---

## Quality

**Confidence Buckets** (thresholds TBD in Stage B):
- **High**: Multiple agreeing sources; registry + enrichment align; explicit role stated
- **Medium**: Single authoritative source (registry-only); partial agreement; inferred role
- **Low**: Enrichment-only with weak confidence; conflicting data; pattern-inferred
- **Cannot Verify**: No data from any source; irreconcilable conflicts; explicit not-found

**Dedupe**: Normalize emails (lowercase, trim); match on name/email/phone; merge agreeing sources (confidence ↑); flag conflicts as `needs_human_review`

**Conflict Resolution**: Same contact + same data → merge (agreement ↑); same contact + different data → flag review; different contacts + different roles → keep both

**Provenance**: Every field traceable to source_url. Output includes `source_urls` mapping field → provider → URL. Zero contacts without attribution.

**"Cannot Verify"**: Return empty contact + `needs_human_review = true` + reason when confidence < threshold or no corroborating data.

---

## Privacy / Compliance

**Will Do**:
- B2B contact lookup only (business addresses, business phone/email)
- Transparent provenance (source_url for every field)
- Flag low-confidence as `needs_human_review`
- Support opt-out/suppression lists
- Honest "cannot verify" rather than guessing

**Will NOT Do**:
- Personal data (home address, personal phone)
- Dark patterns or spoofing
- Infer protected characteristics (gender, age, origin) from name
- Scrape beyond terms of service
- Retain unverifiable data indefinitely

---

## Clarifying Questions

### 1. What is the acceptable risk tolerance (precision vs. recall)?

**Why it matters**: Determines confidence threshold and review volume. Precision-first = few false positives but miss true contacts. Recall-first = catch more but risk wrong recipients.

**Default**: Precision-first. Better to say "cannot verify" than email wrong person (damages relationship, lowers conversion).

**What changes**: If recall-preferred → relax thresholds. If compliance-strict → raise thresholds, increase review queue.

---

### 2. What is the expected throughput (RPS) and data volume in production?

**Why it matters**: Determines sync vs. async processing, storage/caching, infrastructure needs. Low RPS (< 100) = simple sync API. High RPS (> 1000) = distributed queue, read replicas.

**Default**: Low throughput (< 100 RPS), modest volume (thousands); simple stateless synchronous implementation.

**What changes**: If high RPS → load balancing, connection pooling, rate limiting, distributed queue. If massive volume → sharding, read replicas, cache pre-loading. If hybrid (sync + bulk) → dual pipeline design.

---

### 3. How comfortable are you adding new architectural components to scale?

**Why it matters**: Determines monolithic vs. distributed design. Impacts operational complexity, deployment strategy.

**Default**: Minimal new components; simple synchronous single-process design.

**What changes**: 
- If **queues allowed** → async bulk import, decouple API from enrichment, job polling
- If **schedulers allowed** → periodic refresh, background dedup, nightly reports
- If **microservices allowed** → separate enrichment/scorer/formatter services, independent scaling
- If **no new infrastructure** → keep synchronous, optimize for speed, accept throughput limits

---

### 4. What are the success metrics for productionization?

**Why it matters**: Defines KPIs to optimize for (accuracy, coverage, speed, cost, ROI). Drives monitoring/alerting and trade-off decisions.

**Default**: Precision > 80%, coverage > 60%, API response < 5s, < 10% manual review rate.

**What changes**: 
- If precision-critical → FPR < 5%, accept low coverage (30-40%)
- If coverage-critical → find 80%+ of companies, tolerate lower precision
- If speed-critical → P99 < 1s, caching required, simple scoring logic
- If cost-critical → optimize cost per contact, batch over real-time
- If ROI-critical → measure downstream payment conversion, A/B test thresholds

---

### 5. How should confidence scoring work: Rule-based, Traditional ML, or LLM-based?

**Why it matters**: Determines algorithmic approach, training data requirements, infrastructure, explainability, maintenance burden.

**Default**: Rule-based. Simple heuristic (signal aggregation + penalties), transparent, zero training data, fully explainable.

**What changes**:
- If **rule-based** → manual weight tuning; simple; explainable; ceiling ~75-80% precision
- If **traditional ML** → train classifier on labeled data (1000-5000 rows); 2-4 weeks effort; need model serving; ceiling ~85-92% precision
- If **LLM-based** → few-shot prompting (GPT-4/Claude); expensive (~$0.01-0.05/call); 1-3s latency; no training; ceiling ~90-95% precision but high cost
- If **hybrid** → rule-based for obvious cases (70%), ML/LLM for ambiguous (30%); balanced cost/accuracy/explainability

---
