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
    
    dataset_path = Path(__file__).resolve().parent / "dataset.json"
    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    results = run_eval(dataset)
    

def run_prompt(test_case):
    """Merges the prompt and test case input, then returns the result"""
    fmt = get_expected_format(test_case)
    solution_criteria = test_case["solution_criteria"]
    prompt = f"""
Please solve the following task:

{test_case["task"]}

* Focus on tasks that do not require writing much code
* Please respond with a valid {fmt}. No extra explanation unless needed.
"""
    
    messages = []
    add_user_message(messages, prompt)
    output = chat(messages)
    return output

def run_test_case(test_case):
    """Calls run_prompt, then grades the result"""
    output = run_prompt(test_case)
    syntax_score, expected_format, syntax_message = grade_by_code(output, test_case)
    grade_message = grade_by_model(test_case, output)
    model_score = grade_message["score"]
    reasoning = grade_message["reasoning"]
  
    
    score = (syntax_score + model_score) / 2
    print("Syntax Score:", syntax_score, f"({syntax_message})")
    print("Model Score:", model_score)
    print("Avg Score:", score)
    return {
        "test_case": test_case,
        "output": output,
        "syntax_score": syntax_score,
        "syntax_message": syntax_message,
        "model_score": model_score,
        "expected_format": expected_format,
        "reasoning": reasoning,
        "final_score": score
    }

def run_eval(dataset):
    """Loads the dataset and calls run_test_case with each case"""
    results = []
    
    for i, test_case in enumerate(dataset, 1):
        fmt = get_expected_format(test_case)
        print(f"Running test {i}/{len(dataset)} [{fmt}]: {test_case['task'][:60]}...")
        result = run_test_case(test_case)
        results.append(result)
        print(f"  Done test {i}")
    average_score = statistics.mean(result["final_score"] for result in results)
    print(f"Average score: {average_score}")
    print(json.dumps(results, indent=2))
    return results

def grade_by_model(test_case, output):
    # Create evaluation prompt
    eval_prompt = f"""
    You are an expert AWS code reviewer. You should use the Solution criteria to evaluate these Evaluate this AI-generated solution.

    Original Task : 
        Task: {test_case["task"]}
    Solution to evaluate : 
        Solution: {output}

    The critieria to evaluate the solition with : 
        Solution criteria: {test_case["solution_criteria"]}
    
    Provide your evaluation as a structured JSON object with:
    - "score": A number between 1-10
    - "reasoning": A concise explanation of your assessment
    """
    
    messages = []
    add_user_message(messages, eval_prompt)
    add_assistant_message(messages, "```json")
    
    eval_text = chat(messages, stop_sequences=["```"])
    return json.loads(eval_text)

VALID_FORMATS = frozenset({"json", "python", "regex", "xml"})


def get_expected_format(test_case: dict) -> str:
    """Use explicit test_case['format']; fall back to task keyword inference."""
    if "format" in test_case:
        fmt = str(test_case["format"]).strip().lower()
        if fmt in VALID_FORMATS:
            return fmt
        return "unknown"
    return infer_output_format(test_case.get("task", ""))


def grade_by_code(output: str, test_case: dict) -> tuple[int, str, str]:
    fmt = get_expected_format(test_case)
    if fmt == "unknown":
        return 0, fmt, "Missing or invalid format (expected json, python, regex, or xml)"
    valid, message = VALIDATORS[fmt](output)
    score = 10 if valid else 0
    return score, fmt, message


def infer_output_format(task: str) -> str:
    """Fallback when dataset entries omit an explicit format field."""
    t = task.lower()
    if "json" in t:
        return "json"
    if "python" in t or "function" in t:
        return "python"
    if "regular expression" in t or "regex" in t:
        return "regex"
    if "xml" in t:
        return "xml"
    return "unknown"


def extract_answer(text: str) -> str:
    blocks = fenced_code_blocks(text)
    if blocks:
        return blocks[0]
    return text.strip()


def fenced_code_blocks(text: str) -> list[str]:
    return [
        block.strip()
        for block in re.findall(
            r"```(?:\w+)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE
        )
        if block.strip()
    ]


def _extract_json_substring(text: str) -> str | None:
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        if start == -1:
            continue
        end = text.rfind(close_ch)
        if end > start:
            return text[start : end + 1]
    return None


def validate_json(text: str) -> tuple[bool, str]:
    if not text.strip():
        return False, "Empty output"
    last_err = "No JSON found"
    for candidate in (text.strip(), extract_answer(text), _extract_json_substring(text) or ""):
        if not candidate:
            continue
        try:
            json.loads(candidate)
            return True, "Valid JSON"
        except json.JSONDecodeError as e:
            last_err = str(e)
    return False, f"Invalid JSON: {last_err}"


def _extract_python_substring(text: str) -> str | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("def ", "class ", "import ", "from ", "@")):
            return "\n".join(lines[i:]).strip()
    return None


def validate_python(text: str) -> tuple[bool, str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for block in fenced_code_blocks(text):
        _add_candidate(candidates, seen, block)
    _add_candidate(candidates, seen, _extract_python_substring(text) or "")
    _add_candidate(candidates, seen, text.strip())

    last_err = "Empty output"
    for code in candidates:
        try:
            ast.parse(code)
            return True, "Valid Python syntax"
        except SyntaxError as e:
            last_err = f"{e.msg} (line {e.lineno})"
    return False, f"Invalid Python: {last_err}"


def _add_candidate(candidates: list[str], seen: set[str], text: str) -> None:
    text = text.strip()
    if text and text not in seen:
        seen.add(text)
        candidates.append(text)


def _extract_regex_pattern(text: str) -> str:
    text = text.strip()
    quoted = re.search(r'r?["\'](.+?)["\']', text, re.DOTALL)
    if quoted and len(quoted.group(1)) < 500:
        return quoted.group(1)
    backtick = re.search(r"`([^`]+)`", text)
    if backtick:
        return backtick.group(1).strip()
    slash = re.search(r"^/(.+?)/[gimsux]*$", text.strip())
    if slash:
        return slash.group(1)
    for line in text.splitlines():
        line = line.strip()
        if line and not line.lower().startswith(("here", "this", "the ", "use ", "note")):
            return line
    return text


def validate_regex(text: str) -> tuple[bool, str]:
    pattern = _extract_regex_pattern(extract_answer(text) or text)
    if not pattern.strip():
        return False, "No regex pattern found"
    try:
        re.compile(pattern)
        return True, "Valid regular expression"
    except re.error as e:
        return False, f"Invalid regex: {e}"


def _strip_xml_declaration(xml_text: str) -> str:
    xml_text = xml_text.strip().lstrip("\ufeff")
    return re.sub(r"^\s*<\?xml[^?]*\?>\s*", "", xml_text, count=1, flags=re.IGNORECASE)


def _extract_xml_substring(text: str) -> str | None:
    """Extract the main XML document from text (not prose after a code block)."""
    text = text.strip()
    decl = re.search(r"<\?xml[^?]*\?>", text, re.IGNORECASE)
    if decl:
        return text[decl.start() :]
    start = text.find("<")
    if start == -1:
        return None
    end = text.rfind(">")
    if end <= start:
        return None
    return text[start : end + 1]


def _wrap_xml_fragment(xml_text: str) -> str:
    return f"<root>{_strip_xml_declaration(xml_text)}</root>"


def _try_parse_xml(xml_text: str) -> tuple[bool, str]:
    for candidate in (xml_text, _wrap_xml_fragment(xml_text)):
        try:
            ET.fromstring(candidate)
            return True, "Valid XML"
        except ET.ParseError as e:
            last_err = str(e)
    return False, last_err


def validate_xml(text: str) -> tuple[bool, str]:
    if not text.strip():
        return False, "Empty output"

    candidates: list[str] = []
    seen: set[str] = set()
    blocks = fenced_code_blocks(text)
    if blocks:
        for block in blocks:
            _add_candidate(candidates, seen, block)
            snippet = _extract_xml_substring(block)
            if snippet and snippet != block.strip():
                _add_candidate(candidates, seen, snippet)
    else:
        body = extract_answer(text) or text.strip()
        _add_candidate(candidates, seen, body)
        snippet = _extract_xml_substring(body)
        if snippet and snippet != body.strip():
            _add_candidate(candidates, seen, snippet)

    last_err = "No XML found"
    for xml_text in candidates:
        ok, last_err = _try_parse_xml(xml_text)
        if ok:
            return True, "Valid XML"
    return False, f"Invalid XML: {last_err}"


VALIDATORS = {
    "json": validate_json,
    "python": validate_python,
    "regex": validate_regex,
    "xml": validate_xml,
}


if __name__ == "__main__":
    main()