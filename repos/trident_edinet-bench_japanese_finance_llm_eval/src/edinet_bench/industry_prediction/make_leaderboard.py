import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, accuracy_score
import japanize_matplotlib  # noqa
import argparse
import os

plt.rcParams["font.size"] = 18

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


def collect_industry_metrics(
    result_base_dir: str, result_dirs: list[str], sheets: list[str]
):
    """
    Collect industry prediction metrics from multiple result directories

    Args:
        result_base_dir: Base directory for results
        result_dirs: List of result directory names (e.g., ["result_0", "result_1", "result_2"])
        sheets: List of sheets to include

    Returns:
        A dictionary of accuracy metrics for each model
    """
    all_metrics = {}

    for result_dir_name in result_dirs:
        result_dir = os.path.join(result_base_dir, result_dir_name)

        model_names = sorted(list(MODEL_TABLE.keys()))
        for model_name in model_names:
            path = os.path.join(
                result_dir,
                "industry_prediction",
                model_name,
                "_".join(sorted(sheets)) + ".jsonl",
            )

            if not os.path.exists(path):
                print(f"Warning: {path} does not exist")
                continue

            # Initialize predictions and labels
            predictions = []
            labels = []

            # Read and process the JSONL file
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        json_data = json.loads(line)
                        prediction = json_data.get("prediction")
                        label = json_data.get("industry")
                        if prediction is not None and label is not None:
                            predictions.append(prediction)
                            labels.append(label)

                # Compute accuracy
                if predictions and labels:
                    acc = accuracy_score(labels, predictions)

                    # Store metrics
                    model_display_name = MODEL_TABLE[model_name]
                    if model_display_name not in all_metrics:
                        all_metrics[model_display_name] = {"accuracy": []}

                    all_metrics[model_display_name]["accuracy"].append(acc)
            except Exception as e:
                print(f"Error processing {path}: {str(e)}")
    print(all_metrics)
    # Calculate mean and std for each model
    mean_std_metrics = {}
    for model_name, metrics in all_metrics.items():
        mean_std_metrics[model_name] = {}
        for metric_name, values in metrics.items():
            if values:
                mean_std_metrics[model_name][f"{metric_name}_mean"] = np.mean(values)
                mean_std_metrics[model_name][f"{metric_name}_std"] = np.std(values)
            else:
                mean_std_metrics[model_name][f"{metric_name}_mean"] = None
                mean_std_metrics[model_name][f"{metric_name}_std"] = None

    return mean_std_metrics


def create_industry_confusion_matrix(
    result_base_dir: str, result_dir_name: str, model_name: str, sheets: list[str]
):
    """
    Create confusion matrix visualization for industry prediction

    Args:
        result_base_dir: Base directory for results
        result_dir_name: Name of the result directory (e.g., "result_0")
        model_name: Name of the model
        sheets: List of sheets to include
    """
    path = os.path.join(
        result_base_dir,
        result_dir_name,
        "industry_prediction",
        model_name,
        "_".join(sorted(sheets)) + ".jsonl",
    )

    if not os.path.exists(path):
        print(f"Warning: {path} does not exist")
        return None

    # Initialize predictions and labels
    predictions = []
    labels = []

    # Read and process the JSONL file
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            json_data = json.loads(line)
            prediction = json_data.get("prediction")
            label = json_data.get("industry")
            if prediction is not None and label is not None:
                predictions.append(prediction)
                labels.append(label)

    # Compute accuracy
    acc = accuracy_score(labels, predictions)

    # Define label list and mapping
    label_en_map = {
        "食品": "Food",
        "電気・ガス・エネルギー資源": "Energy Resources",
        "建設・資材": "Construction and Materials",
        "素材・化学": "Raw Materials & Chemicals",
        "医薬品": "Pharmaceutical",
        "自動車・輸送機": "Automobiles & Transportation",
        "鉄鋼・非鉄": "Steel & Nonferrous Metals",
        "機械": "Machinery",
        "電機・精密": "Electrical & Precision Instruments",
        "電気・精密": "Electrical & Precision Instruments",
        "情報通信・サービスその他": "IT & Services",
        "運輸・物流": "Transportation & Logistics",
        "商社・卸売": "Trading & Wholesale",
        "小売": "Retail",
        "銀行": "Banks",
        "金融(除く銀行)": "Finance (excluding banks)",
        "不動産": "Real Estate",
    }

    # Convert labels to English
    labels_en = [label_en_map[l] for l in labels]
    preds_en = [label_en_map[p] for p in predictions]
    label_list = list(label_en_map.values())

    cm = confusion_matrix(labels_en, preds_en, labels=label_list)
    disp = ConfusionMatrixDisplay(cm, display_labels=label_list)

    fig, ax = plt.subplots(figsize=(12, 12))  # figsize指定してfig, axを作る
    disp.plot(cmap=plt.cm.Blues, xticks_rotation=90, ax=ax, colorbar=False)
    plt.xlabel("Prediction")
    plt.ylabel("Ground Truth")
    plt.tight_layout()

    os.makedirs(os.path.dirname(path), exist_ok=True)
    plt.savefig(path.replace(".jsonl", "_confusion_matrix.png"), dpi=300)
    plt.close()

    return acc


def make_industry_leaderboard(
    result_base_dir: str, result_dirs: list[str], output_format: str, sheets: list[str]
):
    """
    Make a leaderboard table for industry prediction task with mean and standard deviation of metrics
    """
    # Collect metrics from multiple result directories
    metrics = collect_industry_metrics(result_base_dir, result_dirs, sheets)

    # Create DataFrames for mean and std
    metrics_mean = {}
    metrics_std = {}

    for model_name, model_metrics in metrics.items():
        metrics_mean[model_name] = {
            k.replace("_mean", ""): v
            for k, v in model_metrics.items()
            if k.endswith("_mean")
        }
        metrics_std[model_name] = {
            k.replace("_std", ""): v
            for k, v in model_metrics.items()
            if k.endswith("_std")
        }

    df_mean = pd.DataFrame(metrics_mean)
    df_std = pd.DataFrame(metrics_std)

    # Create the final table with mean ± std format
    leaderboard = pd.DataFrame(index=df_mean.index)

    for model_name in df_mean.columns:
        for metric_name in df_mean.index:
            mean_val = df_mean.loc[metric_name, model_name]
            std_val = df_std.loc[metric_name, model_name]

            if mean_val is not None and std_val is not None:
                leaderboard.loc[metric_name, model_name] = (
                    f"{mean_val:.2f} ± {std_val:.2f}"
                )
            else:
                leaderboard.loc[metric_name, model_name] = "N/A"

    # Save and print the leaderboard
    if output_format == "markdown":
        table = leaderboard.to_markdown(index=True)
    elif output_format == "latex":
        table = leaderboard.to_latex(
            index=True,
            column_format="l" + "c" * len(leaderboard.columns),
        )
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    # Ensure the output directory exists
    os.makedirs(os.path.join(result_base_dir, "industry_prediction"), exist_ok=True)

    with open(
        os.path.join(result_base_dir, "industry_prediction", "leaderboard_mean_std.md"),
        "w",
    ) as f:
        f.write(table)

    print(table)

    # Also create a confusion matrix visualization for one of the result dirs (e.g., result_0)
    # for each model as a representative example
    representative_dir = result_dirs[0]
    for model_name in MODEL_TABLE.keys():
        create_industry_confusion_matrix(
            result_base_dir, representative_dir, model_name, sheets
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create industry prediction leaderboard with mean and std from multiple runs"
    )
    parser.add_argument(
        "--result_base_dir",
        type=str,
        default=".",
        help="Base directory containing result_0, result_1, etc.",
    )
    parser.add_argument(
        "--result_dirs",
        type=str,
        nargs="+",
        default=["result_0", "result_1", "result_2"],
        help="Names of result directories to process",
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
    make_industry_leaderboard(
        args.result_base_dir, args.result_dirs, args.output_format, args.sheets
    )
