---
title: "docs(ml): Out-of-Distribution & Non-Waste Robustness Testing"
labels: ["sprint-2", "ml", "documentation"]
subteam: "ml"
deliverable_branch: "docs/ml/<claimant>/robustness-stress-test"
ticket_url: "https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-out-of-distribution--non-waste-robustness-testing"
---

## 🎯 Objective
Confirm model safety against non-trash objects (hands, faces, laptops, furniture) and extreme lighting conditions, ensuring the model does not hallucinate waste categories on non-waste inputs and that 90%+ of non-trash items are safely rejected with the "uncertain" flag.

## 🔗 Link to Ticket Description
- **Master Plan Ticket:** [Sprint 2: Out-of-Distribution & Non-Waste Robustness Testing](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-out-of-distribution--non-waste-robustness-testing)
- **AI/ML Subteam Plan:** [AI/ML Sprint 2 Plan](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_ml-ai.md#ticket-out-of-distribution--non-waste-robustness-testing)
- **Starter Code Reference:** [starter_code/updated_ml-ai_code.md#ticket-out-of-distribution-stress-test](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/starter_code/updated_ml-ai_code.md#ticket-out-of-distribution-stress-test)

## 📁 Expected Files
- `ml/scripts/stress_test_ood.py`
- `docs/ml/robustness_stress_test.md`

## 📦 Expected Deliverable
- **Deliverable & Branch:** `docs/ml/<claimant>/robustness-stress-test`
- **Stress Test Suite (`ml/scripts/stress_test_ood.py`):**
  - Curate or download a test set of 30 challenging out-of-distribution (OOD) non-waste images (selfies, keyboards, pets, chairs, pitch-black photos, overexposed frames).
  - Pass each image through inference and log predicted class and max softmax confidence probability.
  - Evaluate against the calibrated confidence threshold (e.g., 0.50 cutoff).
  - Verify that ≥ 90% of non-waste inputs fall strictly below the threshold, triggering `uncertain: true`.
- **Robustness Report (`docs/ml/robustness_stress_test.md`):**
  - Document the test dataset composition.
  - Tabulate results: image name, top predicted category, confidence score, and uncertain determination.
  - Analyze false positives (items that incorrectly surpassed the confidence threshold).
  - Provide recommendations for runtime safeguards in the backend.
- **Verification:**
  - Execute `python ml/scripts/stress_test_ood.py`; verify output table confirms ≥ 90% rejection rate for non-waste items.

---

## 💻 Starter Scaffold

### `ml/scripts/stress_test_ood.py`
```python
"""Out-of-distribution (OOD) non-waste robustness stress test runner."""

from pathlib import Path
from PIL import Image
import torch
import torchvision.models as models
import torchvision.transforms as transforms

MODEL_PATH = Path("ml/models/sortify_v2.pth")
OOD_DATA_DIR = Path("data/ood_test")
CATEGORIES = ["compost", "glass", "landfill", "paper", "plastic"]
CONFIDENCE_CUTOFF = 0.50


def load_model(weights_path: Path):
    model = models.mobilenet_v2(weights=None)
    model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, len(CATEGORIES))
    if weights_path.exists():
        model.load_state_dict(torch.load(weights_path, map_location="cpu"))
        print(f"[*] Loaded model from {weights_path}")
    elif Path("ml/models/sortify_mvp_v1.pth").exists():
        fallback = Path("ml/models/sortify_mvp_v1.pth")
        model.load_state_dict(torch.load(fallback, map_location="cpu"))
        print(f"[*] Loaded fallback model from {fallback}")
    else:
        print("[!] No checkpoint found; evaluating uninitialized model.")
    model.eval()
    return model


def run_stress_test():
    preprocess = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    model = load_model(MODEL_PATH)

    if not OOD_DATA_DIR.exists():
        OOD_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[!] Created directory {OOD_DATA_DIR}. Please place 30 non-trash test images inside.")
        return

    image_files = [
        f for f in OOD_DATA_DIR.iterdir()
        if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
    ]

    if not image_files:
        print(f"[!] No images found in {OOD_DATA_DIR}. Add test images to evaluate.")
        return

    print(f"\n--- Running OOD Robustness Stress Test on {len(image_files)} Images ---")
    print(f"{'Image':<30} | {'Top Class':<12} | {'Confidence':<10} | {'Flagged Uncertain?'}")
    print("-" * 75)

    flagged_uncertain_count = 0

    with torch.no_grad():
        for img_path in image_files:
            try:
                img = Image.open(img_path).convert("RGB")
                tensor = preprocess(img).unsqueeze(0)
                output = model(tensor)
                probs = torch.softmax(output, dim=1)[0]
                top_prob, pred_idx = torch.max(probs, dim=0)

                confidence = top_prob.item()
                pred_class = CATEGORIES[pred_idx.item()]
                is_uncertain = confidence < CONFIDENCE_CUTOFF

                if is_uncertain:
                    flagged_uncertain_count += 1

                status_label = "YES (SAFE)" if is_uncertain else "NO (FALSE POSITIVE)"
                print(f"{img_path.name[:28]:<30} | {pred_class:<12} | {confidence * 100:6.2f}%   | {status_label}")
            except Exception as e:
                print(f"{img_path.name[:28]:<30} | ERROR: {e}")

    total = len(image_files)
    safe_rate = (flagged_uncertain_count / total) * 100 if total > 0 else 0
    print("-" * 75)
    print(f"Total Non-Waste Images: {total}")
    print(f"Correctly Flagged Uncertain: {flagged_uncertain_count} ({safe_rate:.1f}%)")
    print(f"Pass Criterion (>= 90% Safe): {'PASSED' if safe_rate >= 90.0 else 'FAILED'}")


if __name__ == "__main__":
    run_stress_test()
```

### Report Outline (`docs/ml/robustness_stress_test.md`)
```markdown
# Sortify — Non-Waste Out-of-Distribution Robustness Stress Test

## 1. Executive Summary
- **Evaluation Date:** [Date]
- **Model Checkpoint:** `sortify_v2.pth` (or `sortify_mvp_v1.pth`)
- **Confidence Threshold:** 0.50 (50.0%)
- **Total OOD Images Evaluated:** 30
- **Overall Rejection / Uncertainty Rate:** XX.X% (Goal: >= 90%)

## 2. Dataset Composition
- 10 Personal devices / electronics (laptop keyboards, phones, headphones)
- 10 Human portraits / hands / clothing
- 5 Household furniture / backgrounds (wooden tables, walls, carpets)
- 5 Extreme lighting conditions (pitch black, direct flashlight glare)

## 3. Results Summary Table
| Category Sample | Image Filename | Top Predicted Class | Max Softmax Prob | Outcome |
|---|---|---|---|---|
| Electronics | `laptop_keyboard.jpg` | plastic | 38.2% | Safe (Uncertain) |
| Portrait | `human_hand.jpg` | compost | 31.4% | Safe (Uncertain) |
| Lighting | `dark_room.jpg` | landfill | 42.1% | Safe (Uncertain) |

## 4. Key Takeaways & Recommendations
- Summary of observations and edge cases where non-trash was incorrectly given high confidence.
- Safeguards to enforce in backend `classify.py`.
```
