from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ErrorExplanation:
    problem: str
    likely_cause: str
    safe_fix: str
    command_to_try: str


class RuleBasedProvider:
    def complete(self, prompt: str, system: str | None = None) -> str:
        _ = system
        if "ModuleNotFoundError" in prompt:
            explanation = explain_error(prompt)
            return format_explanation(explanation)
        return (
            "Rule-based mode is active. I can answer project health, risk, security, and common "
            "Python error questions using local scans."
        )


def explain_error(error_text: str) -> ErrorExplanation:
    text = error_text.strip()

    if "ModuleNotFoundError" in text:
        module = _extract_module_name(text)
        install = f"uv add {module}" if module else "uv add <missing-package>"
        return ErrorExplanation(
            problem="Python cannot import a required module.",
            likely_cause="The dependency is not installed in the active environment or is missing from project metadata.",
            safe_fix="Install the missing package in the project environment, then rerun the command.",
            command_to_try=install,
        )

    if "ImportError" in text:
        return ErrorExplanation(
            problem="A Python import failed.",
            likely_cause="The symbol name, package version, or import path does not match what the code expects.",
            safe_fix="Check the package documentation and verify the installed version before editing imports.",
            command_to_try='uv run python -c "import <module>; print(<module>.__version__)"',
        )

    if "SyntaxError" in text:
        return ErrorExplanation(
            problem="Python found invalid syntax.",
            likely_cause="A line contains malformed Python, often from a missing quote, colon, bracket, or indentation issue.",
            safe_fix="Open the file and line in the traceback, then fix the syntax before rerunning tests.",
            command_to_try="uv run python -m py_compile <file.py>",
        )

    if "PermissionError" in text or "permission denied" in text.lower():
        return ErrorExplanation(
            problem="The process does not have permission for the requested file or operation.",
            likely_cause="The file may be owned by another user, locked, or located in a restricted directory.",
            safe_fix="Use a project-local path and inspect ownership before changing permissions.",
            command_to_try="ls -la <path>",
        )

    if "FileNotFoundError" in text or "No such file or directory" in text:
        return ErrorExplanation(
            problem="A required file or directory was not found.",
            likely_cause="The command is running from the wrong directory or the path is misspelled.",
            safe_fix="Confirm the working directory and verify the referenced path exists.",
            command_to_try="pwd && ls",
        )

    if "AssertionError" in text or ("assert" in text.lower() and "pytest" in text.lower()):
        return ErrorExplanation(
            problem="A test assertion failed.",
            likely_cause="The actual behavior no longer matches the expected behavior encoded in the test.",
            safe_fix="Inspect the failing assertion and update the implementation or test expectation deliberately.",
            command_to_try="uv run pytest -q",
        )

    if "address already in use" in text.lower() or "port already in use" in text.lower():
        return ErrorExplanation(
            problem="The requested network port is already occupied.",
            likely_cause="Another server process is running on the same port.",
            safe_fix="Stop the existing process or start the app on a different port.",
            command_to_try="npx kill-port <port>",
        )

    return ErrorExplanation(
        problem="The error does not match a specific built-in rule.",
        likely_cause="More traceback context is needed to identify the exact cause.",
        safe_fix="Rerun the command with full output and inspect the first application frame in the traceback.",
        command_to_try="uv run pytest -q",
    )


def answer_project_question(question: str, context: str) -> str:
    lowered = question.lower()
    if "deploy" in lowered or "release" in lowered:
        return (
            "Based on local context, deployment readiness depends on passing tests, CI coverage, "
            "documented environment variables, and a reviewed risk scan. Run `nax doctor`, "
            "`nax risk`, and `nax security` before release.\n\n"
            f"Context summary:\n{context}"
        )
    if "health" in lowered or "risk" in lowered or "security" in lowered:
        return (
            "Use the latest local scan results as the source of truth. `nax doctor` measures "
            "project completeness, `nax risk` highlights risky change areas, and `nax security` "
            "checks optional scanners plus built-in secret hygiene.\n\n"
            f"Context summary:\n{context}"
        )
    return (
        "Rule-based mode can answer best when the question is about project health, risk, "
        "security, deploy readiness, or common errors. For deeper code reasoning, configure "
        "the local Ollama provider.\n\n"
        f"Context summary:\n{context}"
    )


def suggest_commit_message(changed_files: list[str], diff_summary: str) -> str:
    lowered = "\n".join(changed_files).lower()
    if any(path.startswith("docs/") or path.endswith(".md") for path in changed_files):
        prefix = "docs"
    elif any("test" in path for path in changed_files):
        prefix = "test"
    elif any(
        Path(path).name in {"pyproject.toml", "uv.lock", "package.json"} for path in changed_files
    ):
        prefix = "chore"
    elif any(path.endswith(".py") for path in changed_files):
        prefix = "feat"
    elif "fix" in lowered or "bug" in lowered:
        prefix = "fix"
    else:
        prefix = "chore"

    subject = "update project tooling"
    if "security" in lowered:
        subject = "improve security checks"
    elif "risk" in lowered:
        subject = "add risk analysis"
    elif "doctor" in lowered:
        subject = "add project health scan"
    elif diff_summary:
        subject = "update local dev tooling"
    return f"{prefix}: {subject}"


def format_explanation(explanation: ErrorExplanation) -> str:
    return (
        f"Problem: {explanation.problem}\n"
        f"Likely Cause: {explanation.likely_cause}\n"
        f"Safe Fix: {explanation.safe_fix}\n"
        f"Command to try: {explanation.command_to_try}"
    )


def _extract_module_name(error_text: str) -> str | None:
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_text)
    if not match:
        return None
    return match.group(1).split(".")[0].replace("_", "-")
