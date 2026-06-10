# ABOUT.md

## Why this role

My core background is full-stack engineering — Python, Node.js, and TypeScript — and most of my recent experience comes from building AI-powered pipelines at Quantiphi: designing the system, evaluating each component in isolation, and documenting the reasoning behind design decisions rather than just shipping the result. That combination — full-stack delivery, component-level evaluation, and written design rationale — is what I plan to bring to AgentCollect's recovery pipelines and enterprise integrations, and the same shift from manual, offshore-style processing to AI-driven workflows that I saw at Quantiphi (50,000+ documents/day) is exactly what AgentCollect is doing for B2B collections.

I've also been actively upskilling on the agentic AI side through project-based learning — I have a long tail of "dead" GitHub repos where I broke things on purpose just to understand them, because that's the part of engineering I enjoy most. One mistake from that process: I used to treat evals as an afterthought on agentic projects, and only understood the real cost of that after a couple of interviews where I couldn't justify why an agent behaved the way it did. Evals and tests are now central to everything I build — including this challenge, where I ran a strict TDD loop with Claude Code and verified every test run myself instead of trusting "looks correct." That's also why AgentCollect's AI-native setup (MCP servers, Claude Code skills, automated QA on every PR) and "disagree and commit, low ego, high output" culture feel like a natural fit rather than a stretch.



## How you work with AI tools

I use Claude Code as a pair-programmer for both implementation and
verification, not just code generation. For this challenge:

- I had Claude follow a strict TDD loop per ticket — failing test first,
  then the minimal implementation, one short-lived branch per ticket merged
  `--no-ff` into `main`. That keeps the diff and the reasoning auditable in
  git history instead of buried in one mega-commit.
- I don't trust "looks correct." When Claude reported the Laravel tickets
  done but couldn't run `php artisan test` (no PHP/Composer available), I
  had it install a portable PHP + Composer toolchain and actually run the
  suite before I'd call the work verified — all 26 tests passed, which is
  what let me trust the implementation.
- I override the model on judgment calls. For TICKET-004's contact finder,
  the v2 decision-tree classifier scored every real-world row "high
  confidence," including one where the registry record clearly didn't match
  the business we were trying to reach. I picked v1 (the more conservative
  rule-based classifier) for the deliverable instead, because "precision
  over recall" was the project's explicit principle — the model's
  higher-confidence answer wasn't the right one.
- After functional work, I run a separate pass for production hygiene
  (`.gitignore` for generated build artifacts, committing `composer.lock`,
  etc.) — "it works" and "it's ready to ship" are two different checks.

## Your last project

### AgentOS

**Repository:** https://github.com/Aditya-Dawadikar/AgentOS

**Tech Stack:** Python, FastAPI, Docker, Pytest, Locust, SQLite

AgentOS is a work-in-progress platform that allows AI agents to submit
computational jobs through an API and execute them inside isolated Docker
containers. The long-term goal is to provide a reliable execution substrate
for AI agents, including job lifecycle management, artifact collection,
observability, scheduling, and resource isolation.

The project started from a simple experiment: a ~10-line Python script that
could launch a Docker container and execute arbitrary code. From there, I
incrementally expanded the system into an API-driven platform that manages
container creation, execution, termination, logging, artifact collection,
and job state tracking.

**One ambiguity I faced and how I resolved it**

One of the biggest ambiguities was deciding whether to introduce a queue and
scheduler from the beginning or keep execution synchronous.

My initial instinct was to build a complete architecture with worker pools,
queues, retries, and scheduling. However, I wasn't sure whether that
complexity was justified before validating the execution model itself.

I chose to keep the first version simple. Each API request directly launches
and manages a container. This let me focus on validating the core workflow
and understanding the system's operational characteristics before
introducing distributed scheduling.

To validate the design, I stress-tested the platform on a 4-vCPU AWS EC2
instance using Locust. The system handled up to approximately 64 concurrent
jobs reliably. Beyond that point, P95 and P99 submission latencies developed
a noticeable long tail, exceeding 10 seconds in some scenarios. The
bottleneck was not job execution itself, but the fact that request handling
and execution were tightly coupled.

Those results pushed me toward the next architectural step: introducing a
queue and worker pool to decouple submission from execution and provide
controlled backpressure.

**One tradeoff I made and why**

I deliberately traded scalability for simplicity in the first version.

Instead of building a distributed scheduling system upfront, I focused on
validating the core execution lifecycle:

Job Submission → Container Execution → Logs & Artifacts → Terminal State

This let me verify that container isolation, artifact collection, lifecycle
management, and failure handling worked correctly before investing in
additional infrastructure.

While this approach limits scalability, it significantly reduced the number
of moving pieces and helped me identify the real bottlenecks through
measurement rather than assumptions.

**One mistake I made and what I changed**

I initially underestimated the importance of testing container lifecycle
behavior.

Launching a container is easy. Reliably managing its lifecycle under failure
scenarios is much harder.

A significant portion of the project ended up being dedicated to testing. I
wrote lifecycle tests using Pytest to verify container creation, execution,
termination, timeout handling, artifact collection, log capture, and cleanup
behavior when containers were launched programmatically through the
platform.

These tests uncovered several edge cases around process termination, state
transitions, and cleanup logic that would have been difficult to diagnose in
production. The experience reinforced my belief that infrastructure projects
require rigorous testing long before they require additional features.

In parallel, I used Locust to stress test the platform and understand how it
behaved under concurrent workloads. This combination of unit testing and
load testing provided much more confidence than manual testing alone.

**One review comment that changed my mind**

While discussing the architecture, I received feedback that I was attempting
to solve future scaling problems before validating the execution model
itself.

My instinct was to immediately introduce queues, worker pools, retries, and
distributed scheduling. The feedback was that complexity should be earned
through evidence rather than anticipation.

That changed how I approached the project. Instead of designing the final
architecture upfront, I focused on building the smallest system that could
execute jobs reliably, adding tests around every lifecycle stage, and
collecting load-testing data to guide future decisions.

The eventual stress-testing results validated that approach and clearly
showed when it was time to move toward a queue-based architecture.

**Note**

I don't currently have a polished demo or UI to share because the project is
still under active development. Most of my effort so far has gone into
execution reliability, testing, observability, and infrastructure
foundations rather than presentation layers.

The repository represents the current state of the system, and the next
major milestone is introducing a dedicated scheduler and worker architecture
to improve throughput and scalability.

## Anything you'd improve about THIS challenge or our CLAUDE.md

A few small frictions I hit working through this repo:

- `CLAUDE.md` says to run `php artisan test --parallel`, but
  `brianium/paratest` isn't in `composer.json`'s `require-dev` — the
  documented command fails on a clean checkout (`composer install` +
  `php artisan test --parallel`). Either add the dependency or drop
  `--parallel` from the doc.
- The root `README.md`'s "Legacy ... do not do both" note is easy to miss
  once a repo's history already contains both the Stage A/B Contact Finder
  *and* the original Laravel tickets — worth being explicit about whether
  doing both is penalized, ignored, or a bonus.
- `ABOUT.md` is a hard requirement ("auto-declined" without it), but it's
  mentioned only once, near the bottom of "What to submit" in
  `challenge/PROBLEM.md` — a one-line callout near the top of `README.md`
  would make it harder to miss.
