from datasets import load_dataset
import json
from edinet_bench.model import MODEL_TABLE
from edinet_bench.utils import extract_json_between_markers
from tqdm import tqdm
import argparse
import os


def process_example(example):
    prompt = (
        r"""
    Please predict the name of company of the securities report, based on the information available in the current year's securities report.
    - The input is extracted from a Japanese company's securities report.
    - Some information may be missing and represented as "-" due to parsing errors.
    - Some attributes are missing and the total does not equal the sum of the parts.
    Respond in the following format:
    JSON:
    ```json
    {
    "reasoning": "string",
    "prediction": "string"
    }
    ```
    The current year's extracted securities report is as follows:
    """
        + example["summary"]
        + example["bs"]
        + example["cf"]
        + example["pl"]
    )
    response = model.get_completion(prompt)
    json_data = extract_json_between_markers(response)
    if json_data is None:
        return None

    return {
        "label": json.loads(example["meta"])["会社名"],
        "prediction": json_data.get("prediction", None),
        "reasoning": json_data.get("reasoning", None),
    }


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


if __name__ == "__main__":
    args = parse_args()

    model = MODEL_TABLE[args.model](
        model_name=args.model,
        system_prompt="You are a helpful assistant.",
    )
    ds = load_dataset("SakanaAI/EDINET-Bench", "fraud_detection", split="test")

    result_list = []

    for example in tqdm(ds):
        result = process_example(example)
        if result is None:
            continue
        result_list.append(result)
    save_dir = os.path.join(args.output_dir, args.model)
    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, "prediction.jsonl"), "w") as file:
        for result in result_list:
            file.write(json.dumps(result, ensure_ascii=False) + "\n")
