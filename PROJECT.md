# IslamicResearchHub Project Plan

## Goals

Build a reliable, maintainable platform for organising and researching Islamic source material. The system will preserve clear provenance, support structured research workflows, and be ready to integrate AI capabilities in a later phase.

The current milestone is intentionally limited to repository scaffolding. OCR, PDF reading, AI features, extraction routines, and all business logic are out of scope until later milestones.

## Architecture

The project uses a layered, modular architecture under `src/islamic_research_hub`:

- `domain`: stable domain models, contracts, and rules.
- `application`: use cases and orchestration between domain and infrastructure.
- `infrastructure`: replaceable technical adapters, including SQLite persistence.
- `interfaces`: delivery adapters such as CLI, web, or API entry points.
- `shared`: cross-cutting utilities and shared types.
- `config`: configuration contracts and settings integration.

Dependencies should point inward: interfaces and infrastructure may depend on application/domain contracts, while the domain remains independent of frameworks and storage. This supports SOLID principles, testing, and later replacement of adapters without changing core policies.

SQLite is the initial persistence choice. Database files belong in `data/` and must not be committed. The `infrastructure/persistence` package is reserved for future repository and database adapters.

## Milestones

1. **Foundation** — repository structure, package boundaries, configuration, test layout, documentation, and development tooling.
2. **Domain design** — define research entities, value objects, and repository contracts with stakeholders.
3. **Persistence** — implement SQLite schema management and repositories.
4. **Application workflows** — implement validated use cases and service layer.
5. **Interfaces** — add a CLI and/or web/API adapter.
6. **Document ingestion** — separately evaluate and add approved document processing capabilities; no extraction code exists at this stage.
7. **AI integration** — introduce provider-agnostic AI ports and adapters only after governance, data handling, and evaluation requirements are agreed.

## Development Roadmap

Before implementation, select dependency-management and quality tools, define configuration sources, establish database migration policy, and agree on domain terminology. New features should be introduced as small, tested modules with clear contracts. Keep framework code at the edge of the system, use dependency inversion for integrations, and add tests alongside each capability.
