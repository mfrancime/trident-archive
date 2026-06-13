import json
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, accuracy_score
import japanize_matplotlib  # noqa
import argparse
import os
from edinet_bench.model import MODEL_TABLE


def parse_args():
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument(
        "--output_dir",
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
    return parser.parse_args()


if __name__ == "__main__":
    # Input file path
    args = parse_args()
    path = os.path.join(
        args.output_dir,
        "industry_prediction",
        args.model,
        "_".join(args.sheets) + ".jsonl",
    )

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

    # Compute and display accuracy
    acc = accuracy_score(labels, predictions)
    print(f"Overall accuracy: {acc:.3f}")

    # Define label list (Japanese industry labels)
    label_list = [
        "食品",
        "電気・ガス・エネルギー資源",
        "建設・資材",
        "素材・化学",
        "医薬品",
        "自動車・輸送機",
        "鉄鋼・非鉄",
        "機械",
        "電機・精密",
        "情報通信・サービスその他",
        "運輸・物流",
        "商社・卸売",
        "小売",
        "銀行",
        "金融(除く銀行)",
        "不動産",
    ]

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
        "情報通信・サービスその他": "IT & Services",
        "運輸・物流": "Transportation & Logistics",
        "商社・卸売": "Trading & Wholesale",
        "小売": "Retail",
        "銀行": "Banks",
        "金融(除く銀行)": "Finance (excluding banks)",
        "不動産": "Real Estate",
    }

    # Set font size before plotting
    plt.rcParams.update({"font.size": 6})
    print(labels)
    print(predictions)
    labels = [label_en_map[label] for label in labels]
    predictions = [label_en_map[pred] for pred in predictions]
    label_list = [label_en_map[label] for label in label_list]
    print(labels)
    print(predictions)
    print(label_list)
    # Create confusion matrix and display it
    cm = confusion_matrix(labels, predictions, labels=label_list)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=label_list)
    disp.plot(cmap=plt.cm.Blues, xticks_rotation=90)

    plt.title(f"Confusion Matrix (Accuracy: {acc:.3f})")
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.tight_layout()
    plt.savefig(path.replace(".jsonl", ".png"), dpi=300)
    plt.show()
