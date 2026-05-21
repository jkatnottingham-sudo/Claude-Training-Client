import ast
import json
import re
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

from anthropic_client import add_user_message, add_assistant_message, chat
from anthropic import Anthropic

client = Anthropic()
model = "claude-haiku-4-5"

def main() -> None:
    
    
    dataset=generate_dataset()
    dataset_path = Path(__file__).resolve().parent / "dataset.json"
    with open(dataset_path, "w") as f:
        dataset = json.dump(dataset, f, indent=2)

def generate_dataset():
    prompt = """
Generate a evaluation dataset for a prompt evaluation. The dataset will be used to evaluate prompts
that generate Python, JSON, XML or Regex specifically for AWS-related tasks. Generate an array of JSON objects,
each representing task that requires Python, JSON, an XML or a Regex to complete.

Example output:
```json
[
    {clear
        "task": "Description of task",
        "format": "json",
        "solution_criteria": "solution"
    },
    
]
```

* Each object must include format: one of json, python, regex, or xml (matching the expected solution type).
* Focus on tasks that can be solved by writing a single Python function, a single JSON object, an XML, or a regular expression.
* Focus on tasks that do not require writing much code
* Each object must include solution_criteria: Should mention what a good solution should look like.

Please generate 4 objects.
"""
    messages = []
    add_user_message(messages, prompt)
    add_assistant_message(messages, "```json")
    response=chat(messages,stop_sequences=["```"])
    print(response)
    return json.loads(response)


if __name__ == "__main__":
    main()