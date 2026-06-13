from datasets import load_dataset
import json
import os


def save_filtered_predictions(output_path):
    # Load dataset
    dataset = load_dataset("SakanaAI/EDINET-Bench", "earnings_forecast", split="test")

    # Extract and filter out None predictions
    filtered_data = [
        {"doc_id": doc_id, "prediction": pred, "label": label}
        for doc_id, pred, label in zip(
            dataset["doc_id"], dataset["naive_prediction"], dataset["label"]
        )
        if pred is not None
    ]

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write filtered results to JSONL
    with open(output_path, "w", encoding="utf-8") as f:
        for item in filtered_data:
            json.dump(item, f, ensure_ascii=False)
            f.write("\n")


if __name__ == "__main__":
    output_file = "result/earnings_forecast/naive_prediction/summary.jsonl"
    save_filtered_predictions(output_file)
