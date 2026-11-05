# ONNX export and numerical parity

Issue #65 exports the trained FP32 model into a single portable ONNX file with
dynamic batch dimensions on both `input` and `output`. The script uses the
current PyTorch export API (`dynamo=True`, `dynamic_shapes`, opset 18), validates
the graph with `onnx.checker`, and compares raw logits against ONNX Runtime CPU.
Every tested element must have absolute difference **strictly below 1e-4**.

## Measured artifact

The checked-in [`sortify_v2.onnx`](../../ml/models/sortify_v2.onnx) uses the
available trained **MobileNetV2 baseline**, `mobilenet_v2.pth` (best epoch 10).
The retrained `sortify_v2.pth` checkpoint was unavailable in this workspace.
The requested output filename does not indicate retraining or deployment of v2
weights. No initialized weights or quantized weights were substituted. Run the
same command with the actual v2 checkpoint to replace the artifact when available.

Source checkpoint SHA256:
`54df0a06150bd004608dd39431b092348da17954b40a3fc3d7ec488406762d0e`.
The [machine-readable report](onnx_export_metrics.json) records artifact size,
SHA256, runtime versions, image filenames/content hashes, and per-case results.

| Input case | Batch size | Maximum absolute logit difference |
|---|---:|---:|
| Seeded synthetic tensors | 1 | 2.0861626e-5 |
| Seeded synthetic tensors | 2 | 1.6450882e-5 |
| Seeded synthetic tensors | 4 | 1.4305115e-5 |
| Real validation photos | 10 | 1.4305115e-5 |

All cases passed. The real photos are deterministic, evenly spaced selections
from the existing validation split, covering all five categories. This verifies
framework parity for those inputs, rather than proving equivalence for every
possible image. No accuracy, latency improvement, or campus robustness result is
claimed by this export. The backend still uses its existing PyTorch loader.

## Reproduce

Install the repository requirements and optional export tools:

```bash
python -m pip install -r requirements.txt -r ml/requirements-onnx.txt
python ml/scripts/export_onnx.py \
  --checkpoint ml/models/mobilenet_v2.pth \
  --image-dir data/processed/val \
  --output ml/models/sortify_v2.onnx \
  --report docs/ml/onnx_export_metrics.json
```

For v2, supply `--checkpoint ml/models/sortify_v2.pth`. Without that flag the
script looks for `sortify_v2.pth`, then `sortify_mvp_v1.pth`, then
`mobilenet_v2.pth` in `ml/models`. Missing weights or real images fail clearly;
the script never exports random weights as an automatic fallback. Training
bundles must contain `model_state_dict` and the canonical `class_names` order.
Bare state dictionaries require an adjacent `classes.json`, as produced by the
existing model packaging script. Architecture and tensor shapes load strictly.
PyTorch deserialization always uses `weights_only=True`.

The script stages the graph and report, checks structure, verifies synthetic
batches 1/2/4 plus up to `--num-images` real photos (default 10), then publishes
the verified files. A failed export/checker/parity run preserves prior files.
The two final replacements are individually atomic; they are not a filesystem
transaction, so an interrupted publication should be checked against the report
SHA256 before use. Other generated model files remain ignored; only the named
reviewed ONNX artifact has a specific Git ignore exception.

## Runtime contract and verification

- Input: float32 `[batch_size, 3, 224, 224]`, RGB, resize short edge to 256,
  center crop 224, divide pixels by 255, normalize by ImageNet mean/std.
- Output: float32 `[batch_size, 5]` raw logits in order
  `compost, glass, landfill, paper, plastic`; apply softmax for probabilities.
- Class order, preprocessing, architecture, and source checkpoint hash are also
  embedded in ONNX metadata. Spatial dimensions remain fixed; only batch varies.
- Tests export both MobileNetV2 and ResNet-18 fixture checkpoints, exercise a
  previously untested batch size, reject wrong/nonfinite runtime outputs, check
  explicit class metadata, preserve previous artifacts on failure, and validate
  the checked-in graph against its report. CI installs the optional ONNX tools
  and runs these tests with the existing ML suite.

Reference: [PyTorch ONNX exporter documentation](https://docs.pytorch.org/docs/stable/onnx_export.html).
