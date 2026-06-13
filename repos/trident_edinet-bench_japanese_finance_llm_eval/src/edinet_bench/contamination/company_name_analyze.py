import json
import argparse
from edinet_bench.model import MODEL_TABLE
from edinet_bench.model import OpenAIModel


def parse_args():
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument(
        "--output_dir",
        type=str,
        default="result/company_name_prediction",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-3-5-sonnet-20241022",
        help="Model name",
        choices=MODEL_TABLE.keys(),
    )

    return parser.parse_args()


def llm_as_a_judge(label: str, prediction: str) -> bool:
    model = OpenAIModel(model_name="gpt-4o-2024-05-13")
    prompt = f"""
    Please evaluate the accuracy of the predicted company name.
    Ground truth: {label}
    Prediction: {prediction}
    Respond with either 0 or 1 based on the following criteria:
    Variations in notation (e.g., presence or absence of "Inc.", full-width/half-width characters, symbols, kana conversions, etc.) are acceptable.
    Return 0 if the prediction clearly refers to a different company.
    Return 1 if the prediction refers to the same company.
    Only output a single number: 0 or 1.
    """
    print(prompt)
    response = model.get_completion(prompt)
    response = response.strip()
    print(response)
    if response not in ["0", "1"]:
        raise ValueError(f"Invalid response: {response}")
    return response == "1"


if __name__ == "__main__":
    args = parse_args()

    path = f"{args.output_dir}/{args.model}/prediction.jsonl"

    labels = []
    predictions = []

    with open(path, mode="r") as f:
        lines = f.readlines()
        for line in lines:
            data = json.loads(line)
            labels.append(data["label"])
            predictions.append(data["prediction"])

    print(labels[0])
    print(predictions[0])

    correct_num = 0

    for label, prediction in zip(labels, predictions):
        score = llm_as_a_judge(label, prediction)
        correct_num += score

    acc = correct_num / len(labels)
    print(round(acc, 4))
