import os
import json
import numpy as np
import pandas as pd
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    ConfusionMatrixDisplay,
    roc_curve,
    roc_auc_score,
)
import matplotlib.pyplot as plt
from argparse import ArgumentParser

DATA_KEY = "summary"


def prepare_dataset(task: str, split: str):
    ds = load_dataset("SakanaAI/EDINET-Bench", task, split=split)
    doc_ids = ds["doc_id"]
    print(ds[0][DATA_KEY])  # デバッグ表示（初期データの確認）

    data_list = [
        {**json.loads(example[DATA_KEY]), "label": int(example["label"])}
        for example in ds
    ]

    return preprocess_data(data_list), doc_ids


def preprocess_data(data_list):
    rows = []
    for data in data_list:
        row = {}
        for key, values in data.items():
            if key == "label":
                row[key] = values
            elif values is not None:
                for year, val in values.items():
                    col_name = f"{key}_{year}"
                    row[col_name] = float(val) if val not in ["－", None] else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def fill_and_align_data(X_train, X_test):
    train_mean = X_train.mean(numeric_only=True)
    X_train.fillna(train_mean, inplace=True)
    X_test.fillna(train_mean, inplace=True)

    constant_cols = X_train.columns[X_train.nunique() <= 1]
    X_train.drop(columns=constant_cols, inplace=True)
    X_test.drop(columns=constant_cols, inplace=True, errors="ignore")

    X_test = X_test.reindex(columns=X_train.columns)
    return X_train, X_test


def evaluate_model(y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred)
    rec = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    print(
        f"Accuracy: {acc:.3f}, Precision: {prec:.3f}, Recall: {rec:.3f}, F1: {f1:.3f}"
    )
    return acc, prec, rec, f1


def plot_confusion_matrix(y_true, y_pred):
    conf_matrix = confusion_matrix(y_true, y_pred)
    print(conf_matrix)
    disp = ConfusionMatrixDisplay(confusion_matrix=conf_matrix)
    disp.plot()
    plt.show()


def plot_roc_curve(y_true, y_proba):
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    auc = roc_auc_score(y_true, y_proba)
    plt.plot(fpr, tpr, label=f"ROC curve (AUC = {auc:.2f})")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC curve")
    plt.legend()
    plt.show()
    print(f"AUC: {auc:.3f}")


def save_predictions(path, y_pred, y_true, probs, test_doc_ids):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w") as f:
        for doc_id, pred, label, prob in zip(test_doc_ids, y_pred, y_true, probs):
            json.dump(
                {
                    "doc_id": doc_id,
                    "prediction": int(pred),
                    "prob": float(prob),
                    "label": int(label),
                },
                f,
                ensure_ascii=False,
            )
            f.write("\n")


def show_feature_importance(model, feature_names):
    importance = model.coef_[0]
    feature_importance = pd.DataFrame(
        {
            "feature": feature_names,
            "importance": importance,
            "abs_importance": np.abs(importance),
        }
    ).sort_values("abs_importance", ascending=False)
    print(feature_importance.to_latex(index=False, float_format="%.3f"))


def parse_args():
    parser = ArgumentParser(description="Logistic Regression for Profit Forecast")
    parser.add_argument(
        "--task",
        type=str,
        required=True,
        choices=["fraud_detection", "earnings_forecast"],
        help="Task name.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="result",
        help="Directory to save the output files.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    # データ読み込み・前処理
    train, _ = prepare_dataset(args.task, split="train")
    test, test_doc_ids = prepare_dataset(args.task, split="test")

    X_train, y_train = train.drop(columns=["label"]), train["label"]
    X_test, y_test = test.drop(columns=["label"]), test["label"]

    X_train, X_test = fill_and_align_data(X_train, X_test)

    feature_names = X_train.columns

    # スケーリング
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # モデル学習
    model = LogisticRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    # 評価と出力
    evaluate_model(y_test, y_pred)
    plot_confusion_matrix(y_test, y_pred)
    plot_roc_curve(y_test, y_pred_proba)
    show_feature_importance(model, feature_names=feature_names)
    save_predictions(
        os.path.join(args.output_dir, args.task, "logistic", f"{DATA_KEY}.jsonl"),
        y_pred,
        y_test,
        y_pred_proba,
        test_doc_ids,
    )


if __name__ == "__main__":
    main()
