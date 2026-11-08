# Sortify — Max's working context

Personal branch: `feat/ml/max/domain-gap` in [zmaxitaxi/Sortify](https://github.com/zmaxitaxi/Sortify).
Team repository: [BoppingNoodles/Sortify](https://github.com/BoppingNoodles/Sortify).
Narrative reviewed: **November 4, 2026 (America/Los_Angeles)**.

## Current work — November 4

- Max requested syncing this branch and completing every open issue assigned to `zmaxitaxi` in the team repository. GitHub confirms two assignments: [#63](https://github.com/BoppingNoodles/Sortify/issues/63) (centralized backend exceptions) and [#65](https://github.com/BoppingNoodles/Sortify/issues/65) (ONNX export and numerical parity). Neither issue has discussion comments yet.
- Merged current team main (`78d0ffc`) into the personal branch without conflicts. #52 and #53 are merged. The personal branch now also includes the two new feature implementations for continuity.
- Main introduced one non-executable Python script with a shebang and five unformatted Python snippets in Sprint 2 issue Markdown. A separate prerequisite tooling commit fixes these inherited Ruff failures; both feature branches share that commit.
- Implementations are submitted as independent PRs [#68](https://github.com/BoppingNoodles/Sortify/pull/68) for #63 and [#69](https://github.com/BoppingNoodles/Sortify/pull/69) for #65. Both target team `main`, request Caden, and exclude this file and all personal context commit history. No direct main pushes were made.

### PR #68 — centralized backend exceptions (issue #63)

- Branch `feat/backend/max/centralized-exceptions`, reviewed head `67b4fab7c86501738beb2e4d2b6c8e96856cf513`. GitHub CI passed; Caden's review is requested.
- Defines public application exceptions and handlers for domain errors, HTTP/framework errors, request validation, and unexpected exceptions. Error responses and OpenAPI now consistently use `{error, code, message}`. Clients previously reading `detail` must migrate to `message`.
- Corrupt/unsupported images return 415; oversized images return 413; model execution errors return 500. Busy inference capacity remains 503 with `Retry-After`; timeouts remain 504. Internal details/tracebacks are logged privately, including unexpected failures outside the route itself. Validation responses do not echo submitted values.
- Full independent backend + ML suite: **250 passed**. Real local Uvicorn requests verified corrupt JPEG → 415, 11 MiB upload → 413, malformed multipart → 400, with healthy 200 after each and a valid-image 200 afterward. That server used its configured mock model and was shut down afterward. Tests also cover route/dependency/middleware exceptions, header preservation and OpenAPI.
- Contract change is intentional under the ticket. Handlers do not promise recovery from process kills or failures after response headers are sent.

### PR #69 — ONNX export and parity (issue #65)

- Branch `feat/ml/max/onnx-export`, reviewed head `2833fb35dc7c4d59b48b85dc9b7b3441fad7d960`. GitHub CI passed (Python lint/tests and frontend sanity); Caden's review is requested. CodeRabbit reports success with automatic review skipped, not a completed code review.
- Safe strict checkpoint loading, canonical classes, shared evaluation preprocessing, current PyTorch `dynamo=True` exporter with dynamic batch axes (`dynamic_shapes`), opset 18, full ONNX checker, and ONNX Runtime CPU comparisons on raw logits. Failed export/checker/parity runs preserve prior artifacts. The model/report replacements are individually atomic, not a two-file transaction; verify the recorded artifact hash after interrupted publication.
- `ml/models/sortify_v2.onnx` is a deliberately tracked 9,106,284-byte portable artifact (narrow ignore exception and binary attributes). Its actual source is the available trained **MobileNetV2 baseline** `mobilenet_v2.pth`, epoch 10, SHA256 `54df0a06150bd004608dd39431b092348da17954b40a3fc3d7ec488406762d0e`. Retrained v2 weights were unavailable locally; do not call this artifact retrained v2 merely because of its required filename. The same script accepts the real v2 checkpoint when supplied.
- Synthetic batches 1/2/4 and ten real validation photos across all five classes passed strict maximum absolute difference <1e-4; maximum measured difference **2.086162567e-5**. Graph embeds class order, preprocessing and provenance; outputs are logits, so clients must apply softmax for probabilities. No model deployment, accuracy improvement or speedup was claimed.
- Full independent backend + ML suite: **245 passed**, including 12 ONNX tests for both supported architectures, additional dynamic batch sizes, invalid/nonfinite runtime outputs, explicit class order, artifact/report consistency and preservation after failure. Reports: `docs/ml/onnx_export_{report.md,metrics.json}`.
- Optional dependencies are in `ml/requirements-onnx.txt`; CI installs them. Local verification used isolated `/private/tmp/sortify-onnx-deps` and `/private/tmp/sortify-test-deps` via `PYTHONPATH`, leaving the older virtual environment unchanged.

Max also requested an explanation of the earlier and current tasks, their design decisions, evidence and limits, and a clear way to discuss the work with a senior engineer.

## Latest PR status — October 29

- PRs [#52](https://github.com/BoppingNoodles/Sortify/pull/52) (quantization) and [#53](https://github.com/BoppingNoodles/Sortify/pull/53) (guest history) were merged on October 28 (Los Angeles time). Their older pending-review notes below describe the earlier development state.
- At Max's request, [PR #54](https://github.com/BoppingNoodles/Sortify/pull/54) was closed **without merging** on October 29. It proposed 53 commits / 58 files from the fork's personal `feat/ml/max/domain-gap` branch into the team's old branch of the same name and included `context.md`. It was not a clean feature PR. Keep this personal branch for context and do not reopen that PR or merge it into team branches. The branch was retained.
- The automatic snapshot below records the last sync; refresh it with the normal sync workflow before relying on its older open/closed PR states.

## Working agreement

- **PRs only. Never push directly to either repository's `main`.** Max explicitly confirmed this is Caden's requirement on October 27, 2026. This overrides the obsolete "Push to Main" section in `AGENTS.md`.
- Keep this file committed only on Max's personal working branch. Never open a PR from that branch directly to team main: Git includes tracked documentation in PRs regardless of `.gitignore` or merge attributes.
- Prepare a clean feature branch from the latest `upstream/main`, containing only the implementation changes and excluding this file. Verify the PR's files and commits before publishing. Do not merge personal context commits into main.
- Use the repository's branch convention, `<type>/<subteam>/max/<feature-name>`, atomic Conventional Commits, the PR template, and Caden (`BoppingNoodles`) as reviewer. Aim for PRs under about 300 lines; explain necessary exceptions.
- Run `ruff check .` and `ruff format --check .` over the whole tree before commits/pushes, plus meaningful tests for the change. Do not silently reformat unrelated team code to make a documentation-only change pass.
- Read this file and the current tickets before starting work. Update the narrative after decisions, completed work, reviews, or new evidence. Automated sync updates the snapshot below; it cannot infer new engineering conclusions.

## Local sync and PR workflow

This workspace is `/Users/maxli/Documents/ChatGPT/Sortify`. `origin` is Max's fork; `upstream` is Caden's team repository. The older checkout `/Users/maxli/Sortify` remains untouched, including its untracked Cursor rules, virtual environment, datasets, and model weights. Its remote names differ (`origin` is the team repository and `fork` is Max's fork), so do not copy commands between checkouts blindly.

Local helpers and hooks live under `.git/sortify/` and `.git/hooks/`; only `context.md` is added to tracked source. They are specific to this checkout and do not travel with a clone.

1. On the personal branch, run **`git sync-context`**. It requires a clean working tree, fetches both repositories, merges remote personal work if present, merges `upstream/main`, refreshes GitHub PR/ticket status and the snapshot below, runs Ruff, and commits the context update. Merge conflicts stop the operation for resolution. Network failures stop the command visibly.
2. Make and verify implementation changes on the personal branch, keeping context updates separate where practical.
3. After syncing and committing work, run **`git prepare-pr feat/ml/max/<feature> "feat(ml): <description>"`**. It creates a new local branch with one clean implementation commit parented directly on `upstream/main`, excluding `context.md` and all personal context commit history. It does not change the current checkout or publish anything. If there are no implementation changes, it refuses to create an empty PR branch.
4. Switch to that clean branch, run the relevant tests, push the named feature branch to `origin`, and open a PR targeting `BoppingNoodles/Sortify:main`, filling the template and requesting Caden's review. Verify `context.md` is absent from both PR files and commits. Never merge the personal branch itself.
5. Return to `feat/ml/max/domain-gap`, run `git sync-context`, and push that named branch to `origin` to back up context. Neither remote main is a push target.

PRs #52 and #53 are merged. PRs #68 and #69 are independent and awaiting review.
Start each further task on a fresh branch from `upstream/main`; `git prepare-pr`
exports the entire personal implementation diff, so do not combine the two
outstanding features into another PR.

The local post-merge hook refreshes the Git snapshot after successful merges on the personal branch; an ordinary merge may therefore leave `context.md` modified. `git sync-context` also refreshes GitHub metadata and commits the update. The pre-push hook blocks updates to `main`, blocks the personal branch going to the team repository, and blocks `context.md` on any other pushed branch. Hooks can be bypassed and GitHub UI operations do not run them: always inspect PR contents. Server-side enforcement would require team repository settings; none were changed.

## Product and architecture

Sortify is a UC Berkeley student project: identify waste from a phone photo, show the bin and disposal guidance for a municipality, and eventually support history, impact statistics, and streaks.

- Mobile: React Native/Expo, React Navigation, screens in `mobile/src/screens`, API client in `mobile/src/services/api.js`.
- Backend: FastAPI at `backend.app.main:app`; Swagger `/docs`, ReDoc `/redoc`, health `/health`, classification `/api/classify`, municipal rules `/api/rules`, history `/api/history`, and standalone `/upload-image`.
- ML: PyTorch/Torchvision scripts in `ml/scripts`, primarily MobileNetV2 now, compared with a frozen-backbone ResNet-18 baseline.
- Persistence on upstream main: merged PR #53 provides guest UUID history, explicit memory/Firestore modes and cursor pagination. Production account authentication remains separate; the guest UUID is a record identifier, not verified identity.
- Canonical labels and checkpoint order: **`compost`, `glass`, `landfill`, `paper`, `plastic`**. Read `class_names` from the checkpoint or `classes.json`; never assume paper is index 0. Inference uses softmax confidence, not raw logits.
- Source datasets, PyTorch checkpoints, and credentials remain ignored and were not copied from the older checkout. Local generated INT8 weights remain ignored. The single reviewed ONNX artifact is tracked intentionally; the source FP32 checkpoint and validation photos were read from the older checkout.

## Max's completed work

| Work | Source and current status | Details |
|---|---|---|
| Week 1 transfer-learning exercise | PRs [#1](https://github.com/BoppingNoodles/Sortify/pull/1), [#2](https://github.com/BoppingNoodles/Sortify/pull/2), closed | Small pretrained ResNet-18 exercise; #2 replaced the initial fork PR. Do not label these as merged. |
| Image preprocessing | PR [#7](https://github.com/BoppingNoodles/Sortify/pull/7), merged | RGB 224×224 outputs, corrupt-image skipping, EXIF orientation, transparency on white. Demo: 100 written, 1 unreadable skipped. |
| Shared-loader ResNet baseline | PR [#12](https://github.com/BoppingNoodles/Sortify/pull/12), merged | Frozen pretrained backbone; augmented shared loaders; save best validation checkpoint with metadata and loss curves. |
| MobileNetV2 benchmark | PR [#19](https://github.com/BoppingNoodles/Sortify/pull/19), merged | Same split/loaders, 10 epochs, confidence across all five bins; contract tests and CI integration. |
| Domain-gap/demo evaluation | PR [#23](https://github.com/BoppingNoodles/Sortify/pull/23), merged | Simulated shadow, dim light, edge clutter on 453 lab photos; choose one qualifying golden item per bin before filling remaining slots. |
| Local image upload | PR [#24](https://github.com/BoppingNoodles/Sortify/pull/24), merged | Streaming upload, size/type/empty checks, safe filenames, local storage, tests. |
| Firestore schema, service, tips, logging | PRs [#25](https://github.com/BoppingNoodles/Sortify/pull/25), [#26](https://github.com/BoppingNoodles/Sortify/pull/26), [#27](https://github.com/BoppingNoodles/Sortify/pull/27), [#28](https://github.com/BoppingNoodles/Sortify/pull/28), closed without individual merges | Their implementation files are present in current upstream main through subsequent integration history. Verify code rather than equating "closed" with "merged." |

The backend work covers typed user/scan record validation and credential-free seed dry runs; `FirestoreService` save/list/stats with injected clients and fake-client tests; category/item-specific disposal tips; and request telemetry for method, path, client, status, and latency. Historical PR test totals (28, 35, 43, 51, 54) belong to those PR versions, not a new verification of today's tree.

## Measured ML results and limits

Source dataset: 3,027 images (paper 997, plastic 482, glass 501, compost 500, landfill 547). Preprocessed to RGB 224×224, split 70/15/15 with seed 42: **2,120 train / 454 validation / 453 test**. Training uses augmentations; validation/test use deterministic evaluation transforms and ImageNet normalization.

| Model | Best epoch | Validation accuracy | Test accuracy | Weights | CPU latency/image |
|---|---:|---:|---:|---:|---:|
| ResNet-18 baseline | 6 | 84.58% | 84.33% | 42.7 MB | 15.42 ms |
| MobileNetV2 | 10 | 88.99% | 88.52% | 8.7 MB | 37.23 ms |

These are the recorded comparable runs in `docs/ml/architecture_comparison.md`. MobileNetV2 was smaller and more accurate; ResNet-18 was faster on that CPU. An earlier unaugmented ResNet 87.42% test result was superseded by the shared-loader run. Roadmap examples such as "74% vs 83%" are not replacements for these measured results.

Domain-gap script: `ml/scripts/domain_gap.py`, tests `ml/tests/test_domain_gap.py`, findings `docs/ml/demo_scanning_guide.md`. Mean confidence drops on clean predictions: **shadow 1.4%, dim 2.9%, clutter 3.7%**. CPU batch size 16 was used after MPS ran out of memory. The selected lab objects were vegetables, cardboard box, green glass bottle, plastic milk jug, and an aluminum can labeled landfill in that dataset. That last label describes the model/dataset and is not verified municipal disposal advice. Golden items had at least 90% confidence on the correct labeled bin under every simulated condition. Crumpling and actual phone-camera validation were not measured.

Kathleen's separate merged campus report (`docs/ml/campus-evaluation-report/`) records **2/25 correct (8%)**, compared with about 89% lab accuracy: roughly **81 percentage points** lower. Seventeen predictions were landfill. This is a small, concerning real-world sample, not proof that the lab perturbation test transfers to campus photos. The report metadata uses lab validation accuracy 0.8899; the architecture comparison's held-out test accuracy is 0.8852. Keep those denominators distinct. Verify checkpoint, label order, and preprocessing before interpreting or extending the campus result.

## Current state and next work

- Team main at this review includes live classify integration (PR #30), campus evaluation (#33), backend tests (#34), MobileNetV2/five-bin reconciliation (#47), and municipal rules integration (#46, head `4e05488`). The latest sync brought shared municipal rules and city-specific classification notes into this personal branch. Caden's config, upload validation, inference-service, and hardening PRs #48–51 were open at review; do not describe those proposals as merged functionality. The automated snapshot gives newer status after a sync.
- **Completed issue [#44 — Dynamic INT8 Model Quantization & Latency Benchmark](https://github.com/BoppingNoodles/Sortify/issues/44)** through merged PR #52, including the user-authorized convolution extension. Both MobileNetV2 and ResNet-18 meet >60% compression and <1-point validation-loss targets. This did not deploy a model.
- Issue #44's ~45 MB → ~12 MB / >60% reduction goal resembles ResNet sizing. The initial dynamic Linear-only runs missed compression. The subsequent calibrated static convolution+Linear runs achieved 71.09% reduction for MobileNetV2 and 74.75% for ResNet-18. Keep architecture-specific sizes and accuracy separate; no serving architecture was silently swapped.
- Ticket-based assignments supersede the old person-by-week schedule. Dataset-v2 curation (#42) is unassigned; retraining-v2 (#43) is assigned to Kathleen. Check live ownership before starting or duplicating work.
- Current backend inference defaults to `backend/app/models/sortify_mvp_v1.pth`, honors `settings.MODEL_PATH`, and returns a scaffold mock prediction when weights are missing. Its default still differs from ML training output paths; do not claim real deployed inference based only on a successful HTTP response.
- Current inference preprocessing resizes directly to 224×224, while shared evaluation uses resize/center crop. Track parity and checkpoint metadata during future integration. No fixes to application code were included here.
- Remaining Sprint 2 backlog includes confidence calibration, out-of-distribution testing, statistics/streaks, frontend integration and deployment. History is merged; centralized errors and ONNX export are implemented in PRs #68/#69 pending review. Do not claim production persistence or new real-world model performance was verified.

## New work and PRs from this session

### PR #52 — calibrated convolution INT8 (issue #44)

Branch: `feat/ml/max/int8-quantization`, based directly on team main, pushed to
Max's fork. [PR #52](https://github.com/BoppingNoodles/Sortify/pull/52) was merged
on October 28 (Los Angeles time). Recorded implementation head before merging:
`dac87e26e815f915507c0873698bd69e35777a61`. **GitHub CI passed for the convolution
update** (Python lint/tests and frontend sanity). Its files/commits exclude personal context.

Max explicitly requested quantizing convolution layers after the three earlier
Linear-only runs missed the size target. The default CLI now uses FX static
per-channel INT8 convolution+Linear weights and training-only calibration.
`--method dynamic` retains the earlier Linear-only experiment. Static mode exits
nonzero if either >60% compression or strictly <1 percentage-point loss fails.

| Model | Calibration images | FP32 → INT8 validation | Reduction | CPU FP32 → INT8 |
|---|---:|---|---:|---|
| MobileNetV2 | 1,024 | 404/454 → 401/454 (88.99% → 88.33%) | 71.09% | 13.524 → 13.335 ms |
| ResNet-18 | 256 | 384/454 → 381/454 (84.58% → 83.92%) | 74.75% | 15.407 → 38.517 ms |

Both lose 0.6608 percentage points and pass both gates. MobileNet shrinks from
9,154,379 to 2,646,491 bytes; ResNet from 44,792,779 to 11,311,915 bytes.
All 52 MobileNet convolutions / 20 ResNet convolutions plus their classifiers
are INT8 (zero FP32 convolution layers remain). This does not establish a
meaningful MobileNet speedup; ResNet was slower on this CPU backend.

Calibration is approximately balanced across the five classes, seed 42, using
training images with shared deterministic transforms. All 454 separate validation
photos are used after reloading the artifact; the held-out test split is unused.
Calibration selection was assessed using validation, so these are not new held-out
or campus performance claims. Reports include calibration path/content hashes,
checkpoint hashes, layer counts, exact bytes and both acceptance flags.

A first naive conversion scrambled quantized channels-last output in ReLU6 in the
installed PyTorch build (16.52% accuracy). An explicit contiguous input before the
quantized clamp fixes the layout issue; a small Conv→ReLU6 regression test checks
numeric output against FP32. Shared observers around Conv→ReLU6 are bounded to
[0,6] to preserve useful precision. With 256 calibration photos MobileNet still
lost 1.54 points (397/454); 1,024 calibration photos reached 401/454 and passed.
The rejected 256-image run is retained in `mobilenet_static_256_metrics.json`.

Successful results: `docs/ml/static_quantization_metrics.json` and
`docs/ml/resnet18_static_quantization_metrics.json`. Full methodology, commands,
limits, and the three historical dynamic runs remain in
`docs/ml/quantization_report.md`. Prior dynamic-only size reductions were 0.087%
(MobileNet one thread), 0.0094% (ResNet), and 0.0366% (MobileNet four threads).

Full independent PR branch suite: **102 passed** (11 quantization cases);
Ruff and whitespace checks passed. Reload tests preserve bit-identical output
for both static architectures and confirm the FP32 input model is unchanged.
The generated `ml/models/sortify_quantized.pth` stays ignored. The current backend
loader remains FP32-only; no quantized model was deployed. No PR #53 changes were
included in the quantization PR.

### PR #53 — guest scan-history persistence (issue #39)

Max explicitly authorized assigning and implementing issue #39 after reviewing
unclaimed tickets. It is now assigned to `zmaxitaxi`.
[PR #53](https://github.com/BoppingNoodles/Sortify/pull/53), branch
`feat/backend/max/scan-history-service`, was merged on October 28 (Los Angeles time).
It is independent of #52, based directly on main, with no context
file or personal context commits. **GitHub CI passed** (Python lint/tests and
frontend sanity checks); both PRs are now merged.

- `HistoryService` saves to `users/{user_id}/scans/{scan_id}` in Firestore mode;
  bounded `limit+1` reads use descending timestamp/document-ID cursors.
- The typed guest record extends the shared schema with UUID IDs, generated scan
  IDs and UTC timestamps, and a bin field. Guest identity uses a device UUID,
  without Bearer login; this is not verified account authentication.
- `GET /api/history` requires `user_id` UUID and accepts `limit` and `cursor`;
  `POST` accepts the record. The old mock Bearer/offset contract was migrated
  explicitly in API docs and tests. Mobile UUID persistence remains client work.
- Default `HISTORY_STORAGE=memory` uses one locked process-local store, no
  Firebase initialization, and no restart/multi-worker durability. Set
  `HISTORY_STORAGE=firestore` and configure the existing Firebase helper for
  persistence. Storage errors return safe 503s without silently switching modes.
- Full independent branch tests: **103 passed**; Ruff passed. Real localhost
  Uvicorn HTTP check: **three POSTs → two scans + cursor → one scan + null cursor**;
  OpenAPI exposes the typed response. Real SDK query construction is tested with
  network operations replaced by doubles. **Live Firestore/emulator persistence
  has not been run** because no credentials or emulator were configured.

Both implementations are present on this personal branch for continuity, while
the two PRs contain only their respective feature. Team main received them through
the PR workflow; this agent never pushed directly to either main branch.

## Reading order and evidence

1. Current GitHub tickets and PRs, especially #63/#65 and PRs #68/#69, plus the generated snapshot. PRs #52/#53 document earlier implementation evidence.
2. `README.md`, `SETUP.md`, `.github/pull_request_template.md`, `.github/workflows/ci.yml`.
3. `weekly_assignments/updated_team_weekly_assignments.md`, `updated_ml-ai.md`, `updated_backend.md`, `updated_frontend.md`, plus their matching `starter_code/updated_*_code.md` files. Scaffolds illustrate intended work; inspect actual implementation before copying them.
4. `docs/ml/architecture_comparison.md`, `docs/ml/demo_scanning_guide.md`, `docs/ml/campus-evaluation-report/{README.md,metrics.json,predictions.json}`.
5. `ml/scripts/{preprocess,dataset,split_data,train_baseline,train_mobilenet,domain_gap,evaluate,export_model}.py`, ML tests, backend services/routers/tests, and `docs/firestore-schema.md`.
6. `docs/IMPLEMENTATION_PLAN.md` for older project rationale. Its timelines and contributor lists may differ from the revised ticket backlog.

This narrative was reconstructed from the repositories, local checkout, commit history, available PR descriptions/discussion, and issues. It does not claim access to unrecorded team conversations or presentation assets.

## Validation and current authorization

- Initial sync verification: `ruff check .` and `ruff format --check .` passed; 91 backend/ML tests passed. The older virtual environment lacked the declared `pydantic-settings` package, so test execution used an isolated temporary install through `PYTHONPATH` without changing that environment.
- Workflow fixture checks passed for snapshot refresh, empty PR refusal, clean PR ancestry and files, main push/deletion blocking, team-repository personal-branch blocking, context file/history blocking, and allowed clean feature/personal pushes.
- After adding convolution quantization and combining both independent features on the personal branch, the full backend/ML suite passed **114 tests** (previously 109 before the five new static cases). Both Ruff checks and whitespace verification passed. The local HTTP verification server was shut down after its successful pagination check.
- Earlier authorization covered #44/#39; those PRs are merged. On November 4 Max authorized syncing the personal branch and completing all current assignments (#63/#65), retaining the PR-only/Caden-review workflow. Both implementations and PRs now exist; the issues stay open until the team's merge/review workflow resolves them.
- Final combined personal branch verification on November 4: **262 backend/ML tests passed**, both whole-tree Ruff checks passed, and whitespace checks passed. Both PRs' current heads passed GitHub CI and have Caden requested. Introduced commit ancestry was checked: #68 has three commits, #69 four; `context.md` is absent from every introduced feature commit. No live Firestore check, retrained v2 checkpoint export, or deployment is claimed.

<!-- sortify-sync:start -->
## Automatic sync snapshot

- Refreshed: `2026-11-08T14:56:51-08:00` (America/Los_Angeles).
- Personal branch: `feat/ml/max/domain-gap`.
- Team main: [`78d0ffca6776`](https://github.com/BoppingNoodles/Sortify/commit/78d0ffca6776895755c1fa949e17604ac4b7d977).
- Team main fully included in personal branch: **yes**.
- Neither remote main is updated by this workflow.

### Recent team main commits

- 78d0ffc Merge pull request #57 from BoppingNoodles/feat/backend/david/municipal-rules-expansion
- c639cfd fix(rules): sort test imports to satisfy ruff linter
- 8d2b8b3 fix(test_rules.py): reformatted
- 2d2ff36 fix(rules): edited Sunnyvale rules with city recycling guide
- 04889e9 chore(issues): add sprint 2 issue templates and publishing script
- 1990c32 test(rules): added parameterized tests for the five Bay Area cities
- 543ca3c feat(rules): moved municipal rules into rules.json and added San Jose and Sunnyvale
- 143be33 Merge pull request #55 from BoppingNoodles/feat/ml/kathleen-maung/model-retraining-v2
- 0f5ce53 fix(ml): implement requested changes and retrain model
- b25d095 feat(ml): Add v2 retraining script
- 1339de6 Merge pull request #53 from zmaxitaxi/feat/backend/max/scan-history-service
- 09f314e chore(backend): merge main into feat/backend/max/scan-history-service and reconcile config

GitHub metadata fetched: `2026-11-08T14:56:51-08:00`.

### Max's PR status

- [#69](https://github.com/BoppingNoodles/Sortify/pull/69) **OPEN** — feat(ml): export ONNX models with strict numerical parity
- [#68](https://github.com/BoppingNoodles/Sortify/pull/68) **OPEN** — feat(backend): centralize safe API errors and recovery
- [#54](https://github.com/BoppingNoodles/Sortify/pull/54) **CLOSED** — Feat/ml/max/domain gap
- [#53](https://github.com/BoppingNoodles/Sortify/pull/53) **MERGED** — feat(backend): persist guest scan history with cursor pagination
- [#52](https://github.com/BoppingNoodles/Sortify/pull/52) **MERGED** — feat(ml): quantize convolutions and meet compression and accuracy targets
- [#28](https://github.com/BoppingNoodles/Sortify/pull/28) **CLOSED** — feat(backend): log method, path, client, status, and latency
- [#27](https://github.com/BoppingNoodles/Sortify/pull/27) **CLOSED** — feat(backend): add item-specific disposal tips to classify
- [#26](https://github.com/BoppingNoodles/Sortify/pull/26) **CLOSED** — feat(backend): read and write user scans through a firestore service
- [#25](https://github.com/BoppingNoodles/Sortify/pull/25) **CLOSED** — feat(backend): define the firestore user and scan contract
- [#24](https://github.com/BoppingNoodles/Sortify/pull/24) **MERGED** — feat(backend): accept local image uploads on /upload-image
- [#23](https://github.com/BoppingNoodles/Sortify/pull/23) **MERGED** — Score lab photos under shadow, dim light, and clutter
- [#19](https://github.com/BoppingNoodles/Sortify/pull/19) **MERGED** — feat(ml): compare MobileNetV2 with the ResNet-18 baseline
- [#12](https://github.com/BoppingNoodles/Sortify/pull/12) **MERGED** — feat(ml): add resnet-18 baseline training script
- [#7](https://github.com/BoppingNoodles/Sortify/pull/7) **MERGED** — feat(ml): Week 2 image preprocessing pipeline
- [#2](https://github.com/BoppingNoodles/Sortify/pull/2) **CLOSED** — feat(ml): Week 1 ResNet-18 transfer learning exercise
- [#1](https://github.com/BoppingNoodles/Sortify/pull/1) **CLOSED** — feat(ml): Week 1 ResNet-18 transfer learning exercise

### Open team PRs

- [#70](https://github.com/BoppingNoodles/Sortify/pull/70) — Add item-specific disposal tips engine and matching
- [#69](https://github.com/BoppingNoodles/Sortify/pull/69) — feat(ml): export ONNX models with strict numerical parity
- [#68](https://github.com/BoppingNoodles/Sortify/pull/68) — feat(backend): centralize safe API errors and recovery
- [#67](https://github.com/BoppingNoodles/Sortify/pull/67) — feat(camera): connect live scan to classification api
- [#56](https://github.com/BoppingNoodles/Sortify/pull/56) — [Frontend] Add API Client Resilience and Scan Error Handling

### Open tickets and owners

- [#66](https://github.com/BoppingNoodles/Sortify/issues/66) — docs(ml): Out-of-Distribution & Non-Waste Robustness Testing (aarav-shah-08)
- [#65](https://github.com/BoppingNoodles/Sortify/issues/65) — feat(ml): PyTorch to ONNX Export & Numerical Parity Verification (zmaxitaxi)
- [#64](https://github.com/BoppingNoodles/Sortify/issues/64) — feat(ml): Empirical Confidence Threshold Calibration (kathleen-maung)
- [#63](https://github.com/BoppingNoodles/Sortify/issues/63) — feat(backend): Centralized Exception Handling & Server Stability (zmaxitaxi)
- [#62](https://github.com/BoppingNoodles/Sortify/issues/62) — feat(backend): Timezone-Aware Daily Active Streak Calculator (davidcontreras-ucb)
- [#61](https://github.com/BoppingNoodles/Sortify/issues/61) — feat(backend): User Eco-Stats Aggregation Endpoint (GET /api/stats) (edward-zhou1)
- [#60](https://github.com/BoppingNoodles/Sortify/issues/60) — feat(backend): Production Multi-Stage Dockerfile & Cloud Deployment (janicedeng)
- [#59](https://github.com/BoppingNoodles/Sortify/issues/59) — feat(frontend): Local Storage Service Abstraction & Data Synchronization (unassigned)
- [#58](https://github.com/BoppingNoodles/Sortify/issues/58) — feat(frontend): History Feed Screen & Stats / Streak Dashboard (unassigned)
- [#38](https://github.com/BoppingNoodles/Sortify/issues/38) — [Backend] Item-Specific Disposal Tips Engine & Item Matching (janicedeng)
- [#37](https://github.com/BoppingNoodles/Sortify/issues/37) — [Frontend] API Client Resilience, Retries & Physical Device Testing (aarav-shah-08)
- [#36](https://github.com/BoppingNoodles/Sortify/issues/36) — [Frontend] Dynamic Waste Result Modal & Bin Color Styling (vumongthanhmai98)
- [#35](https://github.com/BoppingNoodles/Sortify/issues/35) — [Frontend] Connect Live Camera Scan to Classification API (BoppingNoodles)
<!-- sortify-sync:end -->
