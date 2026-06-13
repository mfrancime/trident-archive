import json
import os
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    ConfusionMatrixDisplay,
    roc_curve,
    roc_auc_score,
    matthews_corrcoef,
)
from argparse import ArgumentParser

MODEL_TABLE = {
    "logistic": "Logistic",
    "naive_prediction": "Naive",
    "claude-3-5-sonnet-20241022": "Sonnet-3.5",
    "claude-3-7-sonnet-20250219": "Sonnet-3.7",
    "claude-3-5-haiku-20241022": "Haiku-3.5",
    "gpt-4o-2024-11-20": "GPT-4o",
    "o4-mini-2025-04-16": "o4-mini",
    "deepseek/deepseek-r1": "DeepSeek-R1",
    "deepseek/deepseek-chat": "DeepSeek-V3",
}


def make_leaderboard(result_dir: str, output_format: str, sheets: list[str]):
    # Load the results
    # {"model_name": {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}}
    model_results = {}
    model_names = sorted(list(MODEL_TABLE.keys()))
    for model_name in model_names:
        path = os.path.join(result_dir, model_name, "_".join(sorted(sheets)) + ".jsonl")
        print(path)
        if not os.path.exists(path):
            continue

        with open(path, "r") as f:
            lines = f.readlines()
            predictions = []
            probs = []
            labels = []
            for line in lines:
                json_data = json.loads(line)
                prediction = json_data["prediction"]
                if model_name == "naive_prediction":
                    prob = json_data["prediction"]
                else:
                    prob = json_data["prob"]
                if prob is None:
                    continue
                label = json_data["label"]
                if prediction is None:
                    continue
                probs.append(prob)
                predictions.append(int(prediction))
                labels.append(int(label))

            accuracy = accuracy_score(labels, predictions)
            precision = precision_score(labels, predictions)
            recall = recall_score(labels, predictions)
            f1 = f1_score(labels, predictions)
            mcc = matthews_corrcoef(labels, predictions)
            # Calculate ROC AUC if applicable
            if len(set(labels)) == 2:  # Binary classification
                fpr, tpr, _ = roc_curve(labels, probs)
                roc_auc = roc_auc_score(labels, probs)
            else:
                roc_auc = None
            model_results[MODEL_TABLE[model_name]] = {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "roc-auc": roc_auc,
                "mcc": mcc,
            }
            # save confusion matrix
            plt.figure(figsize=(10, 7))
            conf_matrix = confusion_matrix(labels, predictions)
            disp = ConfusionMatrixDisplay(confusion_matrix=conf_matrix)
            disp.plot()

            plt.title(f"{MODEL_TABLE[model_name]}")
            plt.xlabel("Prediction")
            plt.ylabel("Ground Truth")
            if result_dir.endswith("fraud_detection"):
                labels = ["NonFraud", "Fraud"]
            elif result_dir.endswith("earnings_forecast"):
                labels = ["Decrease", "Increase"]
            else:
                raise ValueError(f"Unsupported task: {result_dir}")
            plt.xticks(ticks=[0, 1], labels=labels)
            plt.yticks(ticks=[0, 1], labels=labels)
            plt.tight_layout()
            plt.savefig(
                os.path.join(
                    result_dir,
                    model_name,
                    os.path.basename(path).replace(".jsonl", ".png"),
                )
            )

    # Create a DataFrame
    leaderboard = pd.DataFrame(model_results)
    # transpose
    if output_format == "markdown":
        table = leaderboard.to_markdown(index=True, floatfmt=".2f")
    elif output_format == "latex":
        table = leaderboard.to_latex(
            index=True,
            float_format="%.2f",
            column_format="l" + "c" * len(leaderboard.columns),
        )
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
    with open(os.path.join(result_dir, "leaderboard.md"), "w") as f:
        f.write(table)
    print(table)


def parse_args():
    parser = ArgumentParser(description="Make leaderboard for fraud detection")
    parser.add_argument(
        "--result_dir",
        type=str,
        default="result",
        help="Directory to save the results",
    )
    parser.add_argument(
        "--task",
        type=str,
        required=True,
        choices=["fraud_detection", "earnings_forecast"],
    )
    parser.add_argument(
        "--output_format",
        type=str,
        default="markdown",
        choices=["markdown", "latex"],
        help="Output format for the leaderboard",
    )
    parser.add_argument(
        "--sheets",
        type=str,
        nargs="+",
        default=[
            "summary",
            "bs",
            "pl",
            "cf",
        ],
        help="Sheets to include in the prompt. Default: summary, bs, pl, cf",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result_dir = os.path.join(args.result_dir, args.task)
    make_leaderboard(result_dir, args.output_format, args.sheets)
