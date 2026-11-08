# ONNX export and numerical parity

Issue #65 exports the trained FP32 model into a single portable ONNX file with
dynamic batch dimensions on both `input` and `output`. The script uses the
current PyTorch export API (`dynamo=True`, `dynamic_shapes`, opset 18), validates
the graph with `onnx.checker`, and compares raw logits against ONNX Runtime CPU.
Every tested element must have absolute difference **strictly below 1e-4**.

## Measured artifact

The checked-in [`sortify_v2.onnx`](../../ml/models/sortify_v2.onnx) uses the
retrained **MobileNetV2 v2** checkpoint, `sortify_v2.pth`, shared by Caden
during review. The checkpoint records epoch 10 as the best epoch.

The source checkpoint SHA256 is
`0f35a570c16d3f5abef216097549ad0146b1fcf24cb600b9500b2dd07b9b60f6`.
The [machine-readable report](onnx_export_metrics.json) records artifact size,
SHA256, runtime versions, image filenames/content hashes, and per-case results.

| Input case | Batch size | Maximum absolute logit difference |
|---|---:|---:|
| Seeded synthetic tensors | 1 | 5.4836273e-6 |
| Seeded synthetic tensors | 2 | 2.8610229e-6 |
| Seeded synthetic tensors | 4 | 4.0531158e-6 |
| Real validation photos | 10 | 1.4543533e-5 |

All cases passed. The real image case uses the same ten photos as the baseline
export, sampled deterministically from the original validation split across
all five categories.

## Reproduce

Place the shared checkpoint at `ml/models/sortify_v2.pth` and run the exporter
with the repository requirements and optional export tools installed.

```bash
python -m pip install -r requirements.txt -r ml/requirements-onnx.txt
python ml/scripts/export_onnx.py \
  --checkpoint ml/models/sortify_v2.pth \
  --image-dir data/processed/val \
  --output ml/models/sortify_v2.onnx \
  --report docs/ml/onnx_export_metrics.json
```

Without `--checkpoint`, the script looks for `sortify_v2.pth`, then
`sortify_mvp_v1.pth`, then
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
