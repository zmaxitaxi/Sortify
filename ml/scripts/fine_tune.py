"""Fine-tune a pretrained ResNet-18 for Sortify's five waste categories.

Uses the shared data loaders from ml/scripts/dataset.py.

Run from the repository root with the virtual environment activated:
    python ml/scripts/fine_tune.py --data-dir data/processed --epochs 15
"""

from __future__ import annotations

import argparse
import copy
import random
from pathlib import Path

import torch
from torch import nn, optim
from torchvision import models

from ml.scripts.dataset import get_dataloaders

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "ml" / "models" / "resnet18_finetuned.pth"


def get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def build_model(num_classes: int) -> nn.Module:
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

    # Freeze the pretrained backbone initially.
    for param in model.parameters():
        param.requires_grad = False

    # Fine-tune the deeper layers.
    for param in model.layer3.parameters():
        param.requires_grad = True

    for param in model.layer4.parameters():
        param.requires_grad = True

    # Replace the ImageNet classifier.
    model.fc = nn.Linear(model.fc.in_features, num_classes)

    return model


def set_train_mode(model: nn.Module) -> None:
    # Preserve BatchNorm statistics in frozen layers.
    model.eval()

    # Train the unfrozen layers and classifier.
    model.layer3.train()
    model.layer4.train()
    model.fc.train()


def run_epoch(
    model: nn.Module,
    loader,
    criterion: nn.Module,
    device: torch.device,
    optimizer=None,
) -> tuple[float, float]:
    training = optimizer is not None

    if training:
        set_train_mode(model)
    else:
        model.eval()

    total_loss = 0.0
    correct = 0
    count = 0

    with torch.set_grad_enabled(training):
        for inputs, labels in loader:
            inputs = inputs.to(device)
            labels = labels.to(device)

            logits = model(inputs)
            loss = criterion(logits, labels)

            if training:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * inputs.size(0)
            correct += (logits.argmax(dim=1) == labels).sum().item()
            count += inputs.size(0)

    if count == 0:
        raise RuntimeError("Cannot evaluate an empty data loader.")

    return total_loss / count, correct / count


def report_test(
    model: nn.Module,
    loader,
    device: torch.device,
    class_names: list[str],
    num_examples: int = 5,
) -> float:
    model.eval()

    correct = 0
    count = 0
    shown = 0

    with torch.no_grad():
        for inputs, labels in loader:
            inputs = inputs.to(device)
            labels = labels.to(device)

            probs = torch.softmax(model(inputs), dim=1)

            correct += (probs.argmax(dim=1) == labels).sum().item()
            count += inputs.size(0)

            for prob, label in zip(probs.cpu(), labels.cpu()):
                if shown >= num_examples:
                    break

                scores = "  ".join(
                    f"{name}={p:.1%}" for name, p in zip(class_names, prob.tolist())
                )

                print(f"  true={class_names[label.item()]:<8} {scores}")
                shown += 1

    if count == 0:
        raise RuntimeError("Cannot evaluate an empty test data loader.")

    return correct / count


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data/processed",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=15,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=1e-3,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    if args.epochs < 1:
        parser.error("--epochs must be at least 1.")
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1.")

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    # Use Kathleen's shared data loaders and preprocessing.
    train_loader, val_loader, test_loader, classes = get_dataloaders(
        args.data_dir,
        batch_size=args.batch_size,
    )

    if not classes:
        raise RuntimeError("The shared data loader returned no classes.")

    device = get_device()

    print(f"Device: {device}")
    print(
        f"Images: train={len(train_loader.dataset)} "
        f"val={len(val_loader.dataset)} "
        f"test={len(test_loader.dataset)}"
    )
    print(f"Classes: {classes}")

    model = build_model(num_classes=len(classes)).to(device)
    criterion = nn.CrossEntropyLoss()

    # Differential learning rates for the pretrained layers and classifier.
    optimizer = optim.Adam(
        [
            {
                "params": model.layer3.parameters(),
                "lr": 1e-5,
            },
            {
                "params": model.layer4.parameters(),
                "lr": 1e-4,
            },
            {
                "params": model.fc.parameters(),
                "lr": args.lr,
            },
        ]
    )

    # Decay learning rates throughout training.
    scheduler = optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=args.epochs,
        eta_min=1e-6,
    )

    # Stop if validation loss fails to improve for three consecutive epochs.
    patience = 3
    epochs_without_improvement = 0
    best_val_loss = float("inf")
    best_val_acc = -1.0
    best_epoch = 0
    best_state = None

    print(f"{'epoch':>5} {'train_loss':>11} {'val_loss':>9} {'val_acc':>8}")

    for epoch in range(1, args.epochs + 1):
        train_loss, _ = run_epoch(
            model,
            train_loader,
            criterion,
            device,
            optimizer,
        )

        val_loss, val_acc = run_epoch(
            model,
            val_loader,
            criterion,
            device,
        )

        print(f"{epoch:>5} {train_loss:>11.4f} {val_loss:>9.4f} {val_acc:>8.2%}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_acc = val_acc
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        # Advance the scheduler once per training epoch.
        scheduler.step()

        if epochs_without_improvement >= patience:
            print(
                f"Early stopping at epoch {epoch}: "
                f"validation loss did not improve for {patience} epochs."
            )
            break

    # Guard against saving an invalid checkpoint.
    if best_state is None:
        raise RuntimeError("Training ended without producing a valid model checkpoint.")

    model.load_state_dict(best_state)

    print(f"Best validation loss: {best_val_loss:.4f} at epoch {best_epoch}")
    print(f"Validation accuracy at best epoch: {best_val_acc:.2%}")

    # Evaluate the best validation-loss checkpoint on the test set.
    print("Test examples (softmax probabilities):")
    test_acc = report_test(
        model,
        test_loader,
        device,
        classes,
    )

    print(f"Test accuracy: {test_acc:.2%} on {len(test_loader.dataset)} images")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "model_state_dict": {key: value.cpu() for key, value in best_state.items()},
            "class_names": classes,
            "best_epoch": best_epoch,
            "val_accuracy": best_val_acc,
            "val_loss": best_val_loss,
            "test_accuracy": test_acc,
        },
        args.output,
    )

    print(f"Saved weights to {args.output}")


if __name__ == "__main__":
    main()
