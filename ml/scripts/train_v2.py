"""Model retraining pipeline for Sortify v2.

Fine-tunes a MobileNetV2 backbone on the augmented dataset v2.

Run from the repo root:
    python ml/scripts/train_v2.py
"""

import json
import sys
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.scripts.dataset import DEFAULT_NUM_WORKERS

DATA_DIR = REPO_ROOT / "data" / "processed_v2"
OUTPUT_MODEL_PATH = REPO_ROOT / "ml" / "models" / "sortify_v2.pth"
HISTORY_PATH = OUTPUT_MODEL_PATH.with_name("sortify_v2_history.json")

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def get_data_loaders(
    data_dir: Path,
    batch_size: int = 32,
    num_workers: int = DEFAULT_NUM_WORKERS,
):
    train_transform = transforms.Compose(
        [
            transforms.RandomResizedCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.1, contrast=0.1),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )

    val_transform = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )

    train_ds = datasets.ImageFolder(data_dir / "train", transform=train_transform)
    val_ds = datasets.ImageFolder(data_dir / "val", transform=val_transform)

    if train_ds.classes != val_ds.classes:
        raise ValueError(
            f"Class parity mismatch between train and val splits: "
            f"train={train_ds.classes}, val={val_ds.classes}"
        )

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers
    )
    return train_loader, val_loader, train_ds.classes


@torch.no_grad()
def evaluate(model, loader, criterion, device, num_classes):
    """Return (val_loss, val_acc, per_class_acc) for the given loader."""
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    class_correct = torch.zeros(num_classes)
    class_total = torch.zeros(num_classes)

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        total_loss += criterion(outputs, labels).item() * labels.size(0)
        preds = outputs.argmax(dim=1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)
        for c in range(num_classes):
            mask = labels == c
            class_total[c] += mask.sum().item()
            class_correct[c] += (preds[mask] == c).sum().item()

    val_loss = total_loss / total if total > 0 else 0.0
    val_acc = correct / total if total > 0 else 0.0
    per_class = (class_correct / class_total.clamp(min=1)).tolist()
    return val_loss, val_acc, per_class


def train_model(epochs: int = 15, lr: float = 1e-4):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader, val_loader, classes = get_data_loaders(DATA_DIR)

    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(classes))
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    history = {"train_loss": [], "val_loss": [], "val_acc": []}
    best_val_acc = 0.0
    best_per_class = None

    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * labels.size(0)

        scheduler.step()
        train_loss = running_loss / len(train_loader.dataset)

        val_loss, val_acc, per_class = evaluate(
            model, val_loader, criterion, device, len(classes)
        )

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        print(
            f"Epoch {epoch + 1}/{epochs} - Train Loss: {train_loss:.4f} "
            f"- Val Loss: {val_loss:.4f} - Val Acc: {val_acc * 100:.2f}%"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_per_class = per_class
            OUTPUT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            checkpoint = {
                "architecture": "mobilenet_v2",
                "model_state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                "class_names": list(classes),
                "best_epoch": epoch + 1,
                "val_accuracy": best_val_acc,
            }
            torch.save(checkpoint, OUTPUT_MODEL_PATH)
            print(f"[*] Saved new best model to {OUTPUT_MODEL_PATH}")

    # Persist the loss/accuracy curves for later plotting.
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)
    print(f"Saved training history to {HISTORY_PATH}")

    # Per-class accuracy of the best checkpoint, to spot weak classes.
    if best_per_class is not None:
        print(f"\nBest val acc: {best_val_acc * 100:.2f}%")
        print("Per-class accuracy (best checkpoint):")
        for name, acc in zip(classes, best_per_class):
            print(f"  {name}: {acc * 100:.2f}%")


if __name__ == "__main__":
    train_model()
