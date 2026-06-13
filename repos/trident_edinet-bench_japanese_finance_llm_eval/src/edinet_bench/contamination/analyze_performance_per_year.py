from datasets import load_dataset
import json
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    matthews_corrcoef,
)
from collections import Counter
import argparse

from edinet_bench.model import MODEL_TABLE
import os


# font size
plt.rcParams["font.size"] = 18


def parse_args():
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument(
        "--task",
        type=str,
        required=True,
        choices=["fraud_detection", "earnings_forecast"],
    )
    parser.add_argument(
        "--result_dir",
        type=str,
        default="result",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-3-5-sonnet-20241022",
        help="Model name",
        choices=MODEL_TABLE.keys(),
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
    parser.add_argument(
        "--system_prompt",
        type=str,
        default="You are a financial analyst.",
        help="System prompt for the model.",
    )

    return parser.parse_args()


# plot fiscal start year bar
def get_fiscal_start_year(example):
    meta = json.loads(example["meta"])
    fiscal_start_year = meta["当事業年度開始日"].split("-")[0]
    return fiscal_start_year


if __name__ == "__main__":
    args = parse_args()

    ds = load_dataset("SakanaAI/EDINET-Bench", args.task, split="test")

    ds = ds.map(lambda x: {"fiscal_start_year": get_fiscal_start_year(x)})
    # doc_id: fiscal_start_year
    doc_id_fiscal_start_year = {}
    for example in ds:
        doc_id = example["doc_id"]
        fiscal_start_year = example["fiscal_start_year"]
        doc_id_fiscal_start_year[doc_id] = fiscal_start_year

    path = os.path.join(
        args.result_dir, args.task, args.model, "_".join(sorted(args.sheets)) + ".jsonl"
    )
    predictions = []
    probs = []
    labels = []
    doc_ids = []
    fiscal_start_years = []
    with open(path, "r") as f:
        lines = f.readlines()
        for line in lines:
            json_data = json.loads(line)
            prediction = json_data["prediction"]
            if prediction is None:
                continue
            predictions.append(int(prediction))
            probs.append(json_data["prob"])
            labels.append(int(json_data["label"]))
            doc_ids.append(json_data["doc_id"])
            fiscal_start_years.append(doc_id_fiscal_start_year[json_data["doc_id"]])

    # Calculate metrics
    roc_auc = roc_auc_score(labels, probs)
    print(roc_auc)

    # Calculate metrics per fiscal year
    metrics_per_year = {}
    print(fiscal_start_years)
    for fiscal_start_year in set(fiscal_start_years):
        indices = [
            i for i, year in enumerate(fiscal_start_years) if year == fiscal_start_year
        ]
        y_true = [labels[i] for i in indices]
        y_pred = [predictions[i] for i in indices]
        y_prob = [probs[i] for i in indices]
        print(fiscal_start_year, len(y_true), len(y_pred), len(y_prob))
        print(Counter(y_true), Counter(y_pred), Counter(y_prob))

        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred)
        recall = recall_score(y_true, y_pred)
        f1 = f1_score(y_true, y_pred)
        mcc = matthews_corrcoef(y_true, y_pred)

        # Calculate ROC AUC if applicable
        if len(set(y_true)) == 2:  # Binary classification
            roc_auc = roc_auc_score(y_true, y_prob)
        else:
            roc_auc = None
            continue

        metrics_per_year[fiscal_start_year] = {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "roc-auc": roc_auc,
            "mcc": mcc,
        }

    # plot metrics per year
    plt.figure(figsize=(10, 6))
    years = sorted(metrics_per_year.keys())
    roc_aucs = [metrics_per_year[year]["roc-auc"] for year in years]
    mccs = [metrics_per_year[year]["mcc"] for year in years]
    plt.plot(years, roc_aucs, label="ROC AUC", marker="o")
    plt.plot(years, mccs, label="MCC", marker="o")
    plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=2)
    plt.grid()

    plt.xlabel("Fiscal Start Year")
    plt.ylabel("Score")
    plt.tight_layout()
    output_dir = os.path.join(args.result_dir, args.task, args.model, "contamination")
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, "_".join(sorted(args.sheets)) + ".png")
    plt.savefig(save_path)
    plt.show()
