# ADR: Cross-service event notifications — deferred, not designed away

**Date:** 2026-07-21
**Status:** Accepted
**Context:** Sparked by "docu-store notifies other services about events — can we have
something similar?" (docu-store is the document/compound-extraction sibling app.)

## Decision

**Do not build a cross-service event bus now.** prot-cellar already has the in-process
domain-event backbone; publishing to other services is a localized addition we make *when
a real consumer exists*, not before.

## Why

1. **No consumer.** Nothing in the ecosystem currently needs to react to prot-cellar's
   catalog changes. A bus with zero subscribers is speculative infrastructure (YAGNI).
2. **The seam already exists.** Every use case does `dispatcher.dispatch_all(events)` after
   commit (`UnitOfWork` → commit → dispatch). Today the only subscriber is `AuditEventHandler`.
   An external publisher is *one more subscriber on the same dispatcher* — not a new subsystem.

## What docu-store actually did (and why we don't copy it)

- **Kafka** (`confluentinc/cp-kafka`, single topic `docu_store_events`) + a dedicated
  `plugin-consumer` process + Temporal for handler idempotency.
- Producer is **fire-and-forget, no outbox** → **at-most-once**, best-effort. Envelope is bare
  JSON `{event_type, sub_type, data}` (no id/timestamp/version).
- It exists to fan out to independently-deployed **enrichment plugins** (e.g. PubChem enrichment)
  without coupling them into the core write path.
- docu-store reaches for Kafka because it *already runs* Kafka + Temporal + EventStoreDB.
  **prot-cellar runs Postgres + valkey + arq.** Standing up Kafka here to obtain *weaker*
  (at-most-once) delivery would be cargo-culting.

## When to build it, and what to build

**Trigger:** the moment a *second* service genuinely needs to react to catalog changes
(e.g. a search index, a chem↔protein cross-linker, an AI enrichment service).

**Minimal design, decided now so it isn't re-litigated:**

- **Transport: Redis Streams on the existing valkey** (`XADD` + consumer groups). Not Kafka.
  Persistent + at-least-once + consumer groups, zero new infra — already strictly better than
  docu-store's at-most-once Kafka.
- **One `ExternalEventPublisher` handler** that serializes the existing `DomainEvent` envelope
  (we already have `event_id` + `occurred_at` — richer than docu-store's bare envelope) to the
  stream. Register it exactly where `AuditEventHandler` is registered.
- **One upgrade knob — a transactional outbox** (event rows written in the *same* UoW
  transaction, relayed by an arq periodic job). Only add this if the consumer cannot tolerate the
  small crash-window between DB-commit and `XADD`. prot-cellar is a source-of-truth catalog, so
  unlike docu-store's best-effort enrichment this knob *may* matter — but add it only when a
  consumer asks for it.

Net effort when triggered: **~1 handler + optionally 1 table + 1 relay job**, versus
docu-store's Kafka + Temporal + dedicated consumer process.

## The seam (where the publisher plugs in)

`dispatcher.register(DomainEvent, ExternalEventPublisher(...))`, added at **both** dispatcher
construction sites:

- `backend/src/protcellar/interface/app.py` (API process — dispatcher comes from the DI container)
- `backend/src/protcellar/infrastructure/ingestion/worker.py` (arq ingestion worker — builds its
  own `EventDispatcher`)

**Gotcha:** domain events are dispatched in **two independent processes**. Bulk imports run in the
arq worker, not the API. A publisher registered in only one process will silently drop half the
events. Register in both.

## Consequences

- No code/infra change today beyond pointer comments at the two seam sites.
- The upgrade path is fixed and cheap; future work starts from this ADR, not a blank page.
- If a consumer never materializes, we've spent nothing.
