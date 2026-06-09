# PLAN.md

## Before We Start
### Key Design Principles

1. **Multi-source redundancy** — No single source is complete; use all three independently and combine signals
2. **Parallel fetching** — Query all sources concurrently to reduce latency
3. **Provenance-first** — Every contact field must be traceable to a source URL (audit trail)
4. **Precision over recall** — Honest "cannot verify" better than false-confident wrong contact
5. **Transparency** — Confidence scores must be explainable (not magic black box)

---

## Sources & Strategy

### Three Data Sources (Independently Fallible)

| Source | Typical Strength | Typical Weakness |
|--------|-----------------|-----------------|
| **Registry** | Legal ownership record, authoritative for owner/founder | Slow to update, incomplete for small biz, no contact method |
| **Listing** | Current phone/business info, recent updates | Generic main line, no individual named, may be stale |
| **Enrichment** | Email/phone linked to business, fast lookup | Aggregated from weak signals, self-reported confidence unreliable |

**Strategy**: Combine signals. Agreement across sources = high confidence. Single weak source = low confidence.



## Data Quality & Confidence Buckets

Rather than concrete rules, we'll define **confidence buckets** (actual thresholds TBD in Stage B):

### Confidence Classification Buckets

1. **High Confidence** (Multiple agreeing sources)
   - Multiple sources independently suggest same contact
   - Registry + enrichment agree on name/email
   - Contact role explicitly stated by at least one source

2. **Medium Confidence** (Single authoritative source)
   - Registry-only result (authoritative but single source)
   - Listing + enrichment partially agree
   - Role inferred from context

3. **Low Confidence** (Single weak or conflicting)
   - Enrichment-only with self-reported low confidence
   - Conflicting data across sources (name mismatch, role ambiguity)
   - Inferred from pattern/heuristic only

4. **Cannot Verify** (No data or unreconcilable conflict)
   - No data from any source
   - All three sources conflict irreconcilably
   - Single source with explicit "not found"

### Data Quality Approaches

**Dedupe** (within and across sources):
- Normalize emails (lowercase, trim whitespace)
- Match on exact name match, email match, or phone match
- Merge agreeing sources to raise confidence
- Flag conflicting names as "needs_human_review"

**Conflict Resolution**:
- Same contact, same data → merge (agreement ↑)
- Same contact, different data → flag for human review
- Different contacts (different email/role) → keep both if roles differ (e.g., one AP, one CFO)

**Role Prioritization** (buckets, not concrete order):
- Primary bucket: Decision-maker for payment (AP, owner, CFO, office manager)
- Secondary bucket: Generic contact with no explicit role
- Tertiary bucket: Unknown/cannot-infer role

---

## Clarifying Questions

### 1. What is the acceptable risk tolerance (precision vs. recall)?

**Why it matters**:
- Determines confidence threshold and "needs_human_review" volume
- Precision-first means few false positives but miss some true contacts
- Recall-first means catch more but risk wrong recipients

**Default assumption**:
- Precision-first: Better to say "cannot verify" than email wrong person (damages relationship, lowers conversion)

**What changes if answered**:
- If recall-preferred: Relax thresholds, accept higher false-positive rate
- If compliance-strict (finance, healthcare): Raise thresholds further, increase manual review

---

### 2. What is the priority order for decision-maker roles, and should we use role-specific tactics?

**Why it matters**:
- Different roles have different data source distributions (AP in enrichment, owner in registry)
- May require different search strategies per role type

**Default assumption**:
- Roles treated equally; same scoring logic for all

**What changes if answered**:
- If AP prioritized: Add email pattern matching (`ap@`, `accounting@`)
- If owner prioritized: Boost registry-sourced results; LinkedIn integration for execs
- If role-specific enrichment: Use different confidence buckets per role

---

### 3. How important is data freshness, and what is the refresh strategy?

**Why it matters**:
- Determines if we cache results, dedupe across runs, skip already-contacted companies
- Affects architecture (stateless vs. stateful)

**Default assumption**:
- For this challenge: one-time bulk processing; data freshness = provider's own timestamp; no refresh logic needed

**What changes if answered**:
- If continuous refresh required: Add caching layer, dedupe across runs, track last-contact date
- If real-time: Stream processing, no caching, immediate suppression checks
- Tech stack: Batch Jobs / Streaming Jobs independent from api servers

---

### 4. What is the expected throughput (RPS) and data volume in production?

**Why it matters**:
- RPS (requests per second) determines if we need synchronous vs. asynchronous processing
- Data volume (total companies to enrich, historical archives) affects storage, caching, and query optimization strategy
- Low RPS (< 10 RPS) → simple synchronous API with in-memory cache; high RPS (> 1000 RPS) → distributed queue, read replicas, batch-oriented design
- Volume affects indexing strategy (in-memory lookup vs. database indexes vs. distributed cache)

**Default assumption**:
- For this challenge: low throughput (< 100 RPS), modest volume (thousands of companies); simple stateless synchronous implementation sufficient
- Single-node processing, no distributed systems needed

**What changes if answered**:
- If high RPS (> 1000): Need load balancing, connection pooling, rate limiting per source, distributed queue (Redis, RabbitMQ) to decouple API from enrichment
- If massive volume (millions of rows): Add database sharding, read replicas, pagination for batch exports, warm cache pre-loading
- If real-time API with batch import: Hybrid design with sync for single-company lookups, async for bulk CSV imports
- Storage: In-memory cache vs. Redis vs. PostgreSQL materialized views, depending on volume and access patterns

---

### 5. How comfortable are you adding new architectural components to scale the service?

**Why it matters**:
- Determines if we stay with a single monolithic synchronous component or introduce queue-based, scheduler-based, or microservice patterns
- Willingness to add infrastructure affects design choices (e.g., can we use background jobs, caching layers, separate worker services?)
- Impacts operational complexity, deployment strategy, and monitoring requirements

**Default assumption**:
- For this challenge: minimal new components; no additional infrastructure beyond what exists
- Simple single-process synchronous design (run enrichment inline, return result immediately)

**What changes if answered**:
- If **queues allowed** (Redis, RabbitMQ, AWS SQS): Design async bulk import pipeline; decouple API request from enrichment processing; support job status polling
- If **schedulers allowed** (cron, Airflow, Temporal): Add periodic refresh cycles for stale contacts; background deduplication; nightly reconciliation reports
- If **microservices allowed**: Separate enrichment service (calls 3 providers), separate scorer service, separate output formatter; independent scaling per service; API gateway orchestrates
- If **no new infrastructure**: Keep design synchronous; optimize for fast response; accept throughput limitations; minimal operational burden

---

### 6. What are the success metrics for productionization?

**Why it matters**:
- Defines what "good" looks like and drives KPIs we optimize for (accuracy, coverage, speed, cost, user satisfaction)
- Determines monitoring/alerting requirements (what do we measure?)
- Affects feedback loops (how do we improve over time?)
- Informs trade-off decisions (optimize for precision? coverage? latency? cost?)

**Default assumption**:
- **Accuracy**: Precision > 80% (false-positive rate < 20%), coverage > 60% (find contacts for 60%+ of companies)
- **Performance**: API response < 5s per company; batch processing > 100 companies/minute
- **User satisfaction**: < 10% manual review rate for scores > 70 (contacts we emit should be mostly correct)
- **Data quality**: 100% provenance tracking; zero contacts without source attribution

**What changes if answered**:
- If **precision-critical** (premium clients, high trust): Metric = false-positive rate < 5%; accept low coverage (30-40%); increase manual review threshold
- If **coverage-critical** (maximize outreach): Metric = find something for 80%+ of companies; accept lower precision; tolerate higher false-positive rate; quality gate at 50+ confidence
- If **speed-critical** (real-time payments): Metric = P99 latency < 1s; may sacrifice some accuracy for speed; require caching; simple confidence logic
- If **cost-critical**: Metric = cost per enriched contact < $X; prioritize cheaper enrichment sources; batch processing over real-time; reduce redundant lookups
- If **ROI-critical**: Metric = downstream conversion (payment success) per enriched contact; A/B test confidence thresholds; measure impact on payment recovery rate

---

### 7. What is the team skillset and size to build and operate this system?

**Why it matters**:
- Determines complexity ceiling (what we can realistically build and maintain)
- Affects architecture decisions (simple sync vs. complex distributed system)
- Influences deployment strategy (simple single-node vs. multi-region, auto-scaling)
- Drives onboarding/knowledge sharing requirements

**Default assumption**:
- **MVP (minimum viable product)**: 2 engineers (1 backend, 1 data), 1 product manager
  - Synchronous API, single data source integration, manual CSV export, basic logging
  - Deployment: single VM or small container cluster
  - Can ship in 4-6 weeks
  
- **Growth phase**: 3-4 engineers (backend, data, QA/testing), 1 DevOps, 1 product manager
  - Multi-source integration, async bulk processing, monitoring/alerting
  - Deployment: containerized, CI/CD pipeline, staged rollouts
  - Can scale to 10K+ companies/day
  
- **Scale phase**: 6-10 engineers (3-4 backend, 2 data/ML, 1-2 DevOps, 1 QA), 1 product manager, 1 data analyst
  - Distributed microservices, ML-based confidence scoring, real-time streaming, A/B testing framework
  - Deployment: multi-region, auto-scaling, feature flags, canary deployments
  - Can scale to 1M+ companies/day with high reliability

**What changes if answered**:
- If **small team (1-2 engineers)**: Keep synchronous, single-source, minimal operational overhead; no distributed systems; simple threshold-based scoring; CSV in/out only
- If **medium team (3-5 engineers)**: Can afford async queues, basic multi-source fusion, monitoring; maybe add 1 dedicated DevOps person
- If **large team (6+)**: Can build microservices, ML models, streaming, multi-region; invest in sophisticated observability, A/B testing, incident response
- If **dedicated platform team available**: Can abstract enrichment as shared service; other teams consume via API; centralize source management and scoring logic
- If **no dedicated DevOps**: Keep infrastructure simple (managed services preferred); avoid self-hosted infrastructure; use Lambda/serverless if possible

---

### 8. How should confidence scoring work: Rule-based, Traditional ML, or LLM-based? What's the investment appetite in model training?

**Why it matters**:
- Determines algorithmic approach, training data requirements, infrastructure needs, and maintenance burden
- Affects explainability (rule-based = transparent, ML = black-box, LLM = interpretable but expensive)
- Influences feedback loop strategy (rules = manual tuning, ML = retraining pipeline, LLM = prompt engineering)
- Impacts latency, cost per request, and error handling

**Default assumption**:
- **Rule-based logic** (for this challenge and MVP):
  - Signal aggregation: registry data = +40pts, cross-source agreement = +20pts, enrichment with high provider confidence = +15pts, role explicitly stated = +10pts
  - Penalties: single weak source = -15pts, conflicting data = -20pts, missing contact method = -10pts
  - Simple, transparent, zero training data needed, fully explainable
  - Threshold: score < 70 → manual review
  - Maintenance: tune weights based on user feedback, no model retraining required

**What changes if answered**:

- **If rule-based preferred** (low investment):
  - Keep simple heuristic scoring, manually tune thresholds based on feedback
  - No training infrastructure needed
  - Easy to explain to customers ("80 points because registry + email agreed on this contact")
  - Maintenance: weekly/monthly weight adjustments based on accuracy metrics
  - Ceiling: may plateau at 75-80% precision; hard to improve beyond this

- **If traditional ML preferred** (medium investment):
  - Approach: Collect labeled dataset (1000-5000 rows: input signals + ground-truth outcome), train classifier (Logistic Regression, Random Forest, XGBoost)
  - Features: signal agreement count, provider confidence scores, source diversity, data freshness, name variance
  - Target: binary (correct contact / incorrect) or multi-class (high / medium / low / cannot_verify)
  - Training effort: 2-4 weeks (data labeling, feature engineering, hyperparameter tuning)
  - Explainability: Feature importance rankings (which signals matter most)
  - Maintenance: Retrain monthly/quarterly as new feedback arrives
  - Infrastructure: Need model serving (sklearn + Flask/FastAPI, or cloud ML service)
  - Ceiling: 85-92% precision; can continuously improve with more data

- **If LLM-based preferred** (high investment + operational risk):
  - Approach: Few-shot prompting (GPT-4, Claude) to reason over signal conflicts and assign confidence
  - Example: "You have: registry says 'Jane Smith, Owner'; enrichment says 'jane.smith@company.com' with 75% confidence; listing says '555-1234'. Is this high/medium/low confidence? Explain."
  - Advantages: Handles nuance, natural reasoning about conflicts, explainable outputs (LLM explains its thinking)
  - Disadvantages: Expensive per request (~$0.01-0.05 per call), latency (1-3s per request), dependent on model updates, requires prompt engineering expertise
  - Training: None needed (zero-shot or few-shot); instead, iterate prompt templates (1-2 weeks experimentation)
  - Infrastructure: API calls to OpenAI/Anthropic; need fallback to rule-based if API fails
  - Maintenance: Monitor token costs, adjust prompts based on user feedback, no retraining
  - Ceiling: 90-95% precision, but at high cost per request

- **Hybrid approach** (best of both worlds, moderate investment):
  - Use rule-based for obvious cases (multi-source agreement → auto-high confidence; no data → auto-cannot-verify)
  - Use ML/LLM only for ambiguous cases (conflicting signals, single weak source)
  - Result: 70% of decisions rule-based (fast, free), 30% ML/LLM-based (accurate on hard cases)
  - Cost: medium, explainability: high, maintenance: moderate

---
