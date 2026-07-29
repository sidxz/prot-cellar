# AI/ML Models — Bring-in Candidates for prot-cellar

Modern (as of 2026-07) AI/ML models mapped to what prot-cellar actually does
(protein/gene target-biology, drug-discovery triage, TB-first + human).
Draft list to revisit — nothing committed yet.

## By app job-to-be-done

### 1. Fill missing 3D structures (protein viewer, structure column)
| Model | Why / notes |
|---|---|
| **ESMFold** | Single-sequence, no MSA, fast — best for bulk-filling structures across a whole proteome. Runs on one GPU. |
| **Boltz-2** (open, MIT) | Co-folds protein **+ ligand** *and* predicts binding affinity in one shot. Open answer to AlphaFold3. High-leverage for a target app. |
| **AlphaFold3** | SOTA complexes, but **weights are non-commercial / server-gated** — bring in only if that fits the use. |
| Chai-1 / OpenFold3 | Open alternatives for self-hosted co-folding. |

### 2. Embeddings for search + annotation transfer (protein/gene dashboards, "find similar target")
| Model | Why |
|---|---|
| **ESM-2** (650M–3B) | Workhorse. Per-protein vectors → semantic similarity search, clustering, feature inputs for downstream ML. |
| **ESM-C** (EvolutionaryScale, 2024) | Newer, better quality-per-param — prefer over ESM-2 for new work. |
| **Foldseek** (not ML, but pairs with above) | Structure-based search once structures exist from §1. |

### 3. Function annotation (EC / GO / functional-category columns already stored)
| Model | Fills |
|---|---|
| **CLEAN** | EC-number prediction, contrastive — strong for the EC column. |
| **DeepGO-SE / ProteInfer** | GO-term prediction where UniProt/Mycobrowser is silent. |
| **SaProt** | Structure-aware PLM — better annotations once §1 gives structures. |

### 4. Target-biology prediction — the actual differentiator (essentiality, vulnerability, selectivity axes)
- No single off-the-shelf model. This is an **ESM-embedding → small classifier/regressor** trained on our own DeJesus/CRISPRi labels. PLM does feature extraction; we own the head. Source of "AI-generated" (blue provenance) rows beyond literature.
- **AlphaMissense** — we have the human proteome; use for the *selectivity/anti-target* axis (human variant pathogenicity). **ESM-1v** zero-shot for TB resistance-mutation effects.

### 5. Druggability / pockets (target triage)
- **P2Rank** (fast, near-drop-in), **PocketMiner** (cryptic pockets). Feed structures from §1.

### 6. Target→ligand (once we cross into compounds)
- **Boltz-2** (affinity, §1 again), **DiffDock-L** (blind docking), **Gnina** (CNN-scored docking).
- **Already-wired MCPs**: **ChEMBL** (bioactivity lookups), **Inductive Bio** (logD/pKa — chem-side, more chem-cellar's lane; public MCP only exposes logD + acidic/basic pKa).

### 7. LLM extraction for the ingestion-plugins feature — start here
- **Claude (Opus 4.8 / Sonnet 5)** via API for structured extraction of essentiality/vulnerability/target facts from papers → typed tables, tagged AI-blue via `generation_method`. Lowest-effort, highest-fit bring-in: matches the plugin architecture already speced. **PubMed + bioRxiv MCPs already connected** for retrieval.

---

## Where to start (laziest high-value order)
1. **Claude extraction plugin** — infra exists, matches spec, shippable soon.
2. **ESMFold** bulk structure fill → unlocks §3/§5 for free.
3. **ESM-C embeddings** → powers similarity search *and* becomes the feature layer for §4.

Almost all of §1–5 are on HuggingFace (HF MCP connected) and self-hostable on one GPU.
