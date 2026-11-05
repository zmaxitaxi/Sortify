---
title: "feat(ml): Empirical Confidence Threshold Calibration"
labels: ["sprint-2", "ml", "analysis"]
subteam: "ml"
deliverable_branch: "feat/ml/<claimant>/threshold-calibration"
ticket_url: "https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-empirical-confidence-threshold-calibration"
---

## 🎯 Objective
Balance precision vs. rejection rate on the campus test dataset so ambiguous, blurry, or low-confidence waste images safely trigger an "Uncertain" notice instead of giving misleading sorting advice.

## 🔗 Link to Ticket Description
- **Master Plan Ticket:** [Sprint 2: Empirical Confidence Threshold Calibration](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-empirical-confidence-threshold-calibration)
- **AI/ML Subteam Plan:** [AI/ML Sprint 2 Plan](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_ml-ai.md#ticket-empirical-confidence-threshold-calibration)
- **Starter Code Reference:** [starter_code/updated_ml-ai_code.md#ticket-confidence-threshold-calibration](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/starter_code/updated_ml-ai_code.md#ticket-confidence-threshold-calibration)

## 📁 Expected Files
- `ml/scripts/calibrate_threshold.py`
- `docs/ml/threshold_calibration_results.md` (or calibration report)

## 📦 Expected Deliverable
- **Deliverable & Branch:** `feat/ml/<claimant>/threshold-calibration`
- **Calibration Script (`ml/scripts/calibrate_threshold.py`):**
  - Load the fine-tuned model checkpoint (`ml/models/sortify_v2.pth` or `sortify_mvp_v1.pth`).
  - Run inference over the test dataset (`data/processed_v2/test`).
  - Evaluate softmax confidence score distributions at 0.40, 0.50, and 0.60 cutoffs.
  - Compute precision (accuracy of accepted predictions) and rejection rate for each threshold.
- **Handoff to Backend:**
  - Select optimal threshold (e.g. 0.50) where items with < 50% confidence return `"uncertain": true` with advice to check physical bin signs.
  - Document findings and provide threshold constant to backend team for integration into `POST /api/classify`.
- **Verification:**
  - Verify that clear, high-quality images pass with high confidence while ambiguous/blurry photos are rejected with the uncertain flag.

---

## 💻 Starter Scaffold

### `ml/scripts/calibrate_threshold.py`
```python
"""Evaluates precision and rejection rates across different confidence cutoffs."""

from pathlib import Path
import torch
import torchvision.datasets as datasets
import torchvision.models as models
import torchvision.transforms as transforms


def evaluate_thresholds(
    model_path: Path = Path("ml/models/sortify_v2.pth"),
    test_dir: Path = Path("data/processed_v2/test"),
):
    transform = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    if not test_dir.exists():
        print(f"[!] Test directory not found at {test_dir}. Please run dataset split first.")
        return

    dataset = datasets.ImageFolder(test_dir, transform=transform)
    loader = torch.utils.data.DataLoader(dataset, batch_size=1, shuffle=False)

    num_classes = len(dataset.classes)
    model = models.mobilenet_v2(weights=None)
    model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, num_classes)

    if model_path.exists():
        state = torch.load(model_path, map_location="cpu")
        model.load_state_dict(state)
        print(f"[*] Loaded model checkpoint from {model_path}")
    else:
        print(f"[!] Checkpoint {model_path} not found. Running with uninitialized weights for scaffolding test.")

    model.eval()

    thresholds = [0.40, 0.50, 0.60]
    results = {t: {"accepted": 0, "correct": 0, "rejected": 0} for t in thresholds}

    with torch.no_grad():
        for img, label in loader:
            output = model(img)
            probs = torch.softmax(output, dim=1)[0]
            top_prob, pred = torch.max(probs, dim=0)

            for t in thresholds:
                if top_prob.item() >= t:
                    results[t]["accepted"] += 1
                    if pred.item() == label.item():
                        results[t]["correct"] += 1
                else:
                    results[t]["rejected"] += 1

    print("\n--- Confidence Threshold Calibration Results ---")
    for t in thresholds:
        acc = (
            results[t]["correct"] / results[t]["accepted"] * 100
            if results[t]["accepted"] > 0
            else 0
        )
        rej_rate = results[t]["rejected"] / len(dataset) * 100 if len(dataset) > 0 else 0
        print(
            f"Cutoff {t:.2f} -> Precision: {acc:.2f}% | Rejection Rate: {rej_rate:.2f}% | Accepted: {results[t]['accepted']}/{len(dataset)}"
        )


if __name__ == "__main__":
    evaluate_thresholds()
```
