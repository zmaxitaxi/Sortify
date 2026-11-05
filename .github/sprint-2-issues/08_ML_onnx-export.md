---
title: "feat(ml): PyTorch to ONNX Export & Numerical Parity Verification"
labels: ["sprint-2", "ml", "performance"]
subteam: "ml"
deliverable_branch: "feat/ml/<claimant>/onnx-export"
ticket_url: "https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-pytorch-to-onnx-export--numerical-parity-verification"
---

## 🎯 Objective
Export the trained PyTorch model weights to vendor-neutral ONNX format for accelerated, portable, and low-latency inference across diverse deployment and runtime environments.

## 🔗 Link to Ticket Description
- **Master Plan Ticket:** [Sprint 2: PyTorch to ONNX Export & Numerical Parity Verification](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-pytorch-to-onnx-export--numerical-parity-verification)
- **AI/ML Subteam Plan:** [AI/ML Sprint 2 Plan](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_ml-ai.md#ticket-pytorch-to-onnx-export--numerical-parity-verification)
- **Starter Code Reference:** [starter_code/updated_ml-ai_code.md#ticket-onnx-export--parity-check](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/starter_code/updated_ml-ai_code.md#ticket-onnx-export--parity-check)

## 📁 Expected Files
- `ml/scripts/export_onnx.py`
- `ml/models/sortify_v2.onnx`

## 📦 Expected Deliverable
- **Deliverable & Branch:** `feat/ml/<claimant>/onnx-export`
- **Export Script (`ml/scripts/export_onnx.py`):**
  - Load trained PyTorch checkpoint (`ml/models/sortify_v2.pth` or `sortify_mvp_v1.pth`) in evaluation mode.
  - Export PyTorch compute graph to `ml/models/sortify_v2.onnx` with dynamic batch axes (`{"input": {0: "batch_size"}, "output": {0: "batch_size"}}`) using `torch.onnx.export`.
  - Validate ONNX model structural integrity using `onnx.checker.check_model()`.
- **Numerical Parity Verification:**
  - Initialize an `onnxruntime.InferenceSession` with the exported `.onnx` model.
  - Feed identical synthetic and real tensors into both the PyTorch model and the ONNX Runtime session.
  - Calculate maximum absolute element-wise difference: `diff = np.max(np.abs(pytorch_outs - ort_outs))`.
  - Assert that `diff < 1e-4` to guarantee zero numerical divergence between frameworks.
- **Verification:**
  - Run `python ml/scripts/export_onnx.py`; confirm script reports parity test passed within tolerance.

---

## 💻 Starter Scaffold

### `ml/scripts/export_onnx.py`
```python
"""Export PyTorch weights to ONNX format with parity verification."""

from pathlib import Path
import numpy as np
import onnx
import onnxruntime as ort
import torch
import torchvision.models as models

PYTORCH_MODEL_PATH = Path("ml/models/sortify_v2.pth")
ONNX_OUTPUT_PATH = Path("ml/models/sortify_v2.onnx")


def export_and_verify():
    print("[ONNX Export] Loading PyTorch model...")
    num_classes = (
        5  # Canonical 5-bin taxonomy: compost, glass, landfill, paper, plastic
    )
    model = models.mobilenet_v2(weights=None)
    model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, num_classes)

    if PYTORCH_MODEL_PATH.exists():
        model.load_state_dict(torch.load(PYTORCH_MODEL_PATH, map_location="cpu"))
        print(f"[*] Loaded weights from {PYTORCH_MODEL_PATH}")
    elif Path("ml/models/sortify_mvp_v1.pth").exists():
        fallback = Path("ml/models/sortify_mvp_v1.pth")
        model.load_state_dict(torch.load(fallback, map_location="cpu"))
        print(f"[*] Fallback to {fallback}")
    else:
        print("[!] No checkpoint found; exporting initialized model structure.")

    model.eval()

    dummy_input = torch.randn(1, 3, 224, 224)
    ONNX_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"[ONNX Export] Exporting graph to {ONNX_OUTPUT_PATH}...")
    torch.onnx.export(
        model,
        dummy_input,
        ONNX_OUTPUT_PATH,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
    )

    # Validate ONNX model integrity
    onnx_model = onnx.load(str(ONNX_OUTPUT_PATH))
    onnx.checker.check_model(onnx_model)
    print("[ONNX Export] Model structural integrity check passed.")

    # Parity check
    ort_session = ort.InferenceSession(str(ONNX_OUTPUT_PATH))
    ort_inputs = {ort_session.get_inputs()[0].name: dummy_input.numpy()}
    ort_outs = ort_session.run(None, ort_inputs)[0]

    with torch.no_grad():
        pytorch_outs = model(dummy_input).numpy()

    diff = float(np.max(np.abs(pytorch_outs - ort_outs)))
    print(f"[ONNX Export] Maximum numerical difference: {diff:.6e}")
    assert diff < 1e-4, (
        f"Parity check failed: output difference ({diff}) exceeds tolerance (1e-4)."
    )
    print("[*] Parity verification passed: PyTorch and ONNX Runtime match within 1e-4!")


if __name__ == "__main__":
    export_and_verify()
```
