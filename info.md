Role and objective

Act as a senior AI Evaluation Engineer, SDET, and Python software architect.

Your mission is to design, implement, test, and document a real, portfolio-quality LLM evaluation and testing framework that I can use to demonstrate practical skills when applying for AI QA Engineer, AI Evaluation Engineer, and SDET positions.

Do not just give me a tutorial, a project plan, or code snippets. Actually build the working project in the current workspace.

1. Project concept

Build FactoryGuard AI Eval: an automated testing and evaluation framework for an AI assistant that answers questions about industrial safety procedures using a collection of factory safety documents.

The system must evaluate whether the assistant:

Gives accurate answers supported by the source documents.
Refuses to invent answers when information is missing.
Handles ambiguous questions and conflicting information.
Resists prompt injection and attempts to reveal confidential information.
Uses tools correctly when tools are available.
Maintains acceptable quality when prompts, models, or documents change.

The project must be useful as an actual engineering portfolio project, not a superficial demonstration.

2. Technology stack

Prefer these technologies:

Python 3.12 or a compatible stable version.
Pytest for automated tests.
Promptfoo for LLM evaluation and adversarial testing, where appropriate.
Pydantic for validation and typed data models.
FastAPI for a small API, if it adds practical value.
GitHub Actions for continuous integration.
SQLite or local JSON/JSONL files for reproducible test datasets and results.
Ruff for linting and formatting.
TypeScript only where it adds genuine value.

Use stable, compatible dependencies. Avoid unnecessary frameworks, cloud services, and infrastructure.

The project must support two modes:

Offline mode: deterministic tests that run without API keys, paid services, or internet access.
Live LLM mode: optional evaluation against a real model through a configurable provider, using environment variables for credentials.

Do not require paid APIs to demonstrate the core project.

3. Core features

Implement the following features as working software.

A. Evaluation dataset

Create at least 40 realistic test cases covering:

Normal questions with answers available in the documents.
Questions with insufficient supporting information.
Ambiguous and misleading questions.
Contradictory source information.
Prompt injection attempts.
Requests for confidential information.
Incorrect or malicious instructions embedded in retrieved documents.
Tool-use and tool-selection edge cases, if tool use is implemented.

Each test case must have a stable ID, category, input, expected behavior, and evaluation criteria.

Use fictional factory documents and synthetic confidential data. Do not include real company secrets or sensitive personal information.

B. Evaluation harness

Build a reusable Python evaluation runner that:

Loads and validates test cases.
Executes test cases against the assistant.
Records outputs and evaluation results.
Applies deterministic assertions where possible.
Supports optional model-based judging.
Produces machine-readable JSON results and a readable summary.
Handles timeouts, malformed outputs, and provider errors gracefully.

A test must never pass merely because the model returned a non-empty response.

C. Evaluation rubric and LLM-as-judge

Create a documented scoring rubric for:

Factual correctness.
Grounding in source documents.
Appropriate refusal when evidence is insufficient.
Security and confidentiality.
Following the user's legitimate instructions.

Use structured scoring with explicit pass/fail thresholds and explanations.

Implement an optional LLM judge that returns validated structured output.

Create a human-labeled calibration dataset of approximately 30 examples. Treat these labels as initial reference annotations, document their limitations, and compare judge decisions against them using agreement rate and a confusion matrix.

Do not claim the judge is reliable without reporting measured results. Do not use the judge as the only evaluator for security-critical assertions.

D. Regression testing

Implement automated regression tests that detect:

Reduced evaluation pass rates.
Newly introduced safety failures.
Changes in refusal behavior.
Missing or unsupported claims.
Changes in latency and estimated cost in live mode, when those measurements are available.

Save evaluation results so that a new run can be compared with a baseline.

Clearly distinguish actual measured values from estimates and unavailable metrics.

E. Security and adversarial testing

Implement tests for:

Direct and indirect prompt injection.
Attempts to override system instructions.
Attempts to disclose synthetic confidential data.
Malicious instructions inside retrieved documents.
Requests to fabricate safety procedures.
Unsafe or unauthorized tool calls, if tools are implemented.

Use synthetic data and safe test scenarios. Verify that sensitive information is not disclosed and that untrusted document instructions do not override the assistant's policy.

F. CI/CD

Configure GitHub Actions to run the offline test suite automatically on pushes and pull requests.

The workflow must:

Install dependencies reproducibly.
Run linting and automated tests.
Run the offline evaluation suite.
Publish or retain machine-readable evaluation results where practical.
Fail when defined critical regression thresholds are breached.

CI must not require live LLM credentials.

G. Statistics and reporting

Generate a report containing:

Number of test cases executed.
Overall pass rate.
Pass rate by category.
Failure counts and representative failure details.
Judge/human agreement metrics when available.
Run-to-run variability when repeated runs exist.
Latency and estimated cost for live runs when measurable.

Clearly report sample sizes. Do not make unsupported statistical claims or treat a small test dataset as proof of general model reliability.

H. Developer experience

Provide simple commands to:

Install the project.
Run unit tests.
Run the offline evaluation.
Compare results with a baseline.
Run optional live-model evaluations.
Generate the evaluation report.

A new developer should be able to start the project by following the README without needing to ask me for missing instructions.

4. Engineering quality

Treat this as production-minded software, not a collection of scripts.

Requirements:

Clear module boundaries and type hints.
Meaningful error handling and logging.
Configuration through environment variables and configuration files.
No hardcoded API keys or secrets.
No unnecessary abstractions or dependencies.
Tests for both expected behavior and failure scenarios.
Reproducible offline results.
Useful documentation explaining design decisions and limitations.
No fake integrations, placeholder implementations, or claims that unimplemented features work.

Keep the implementation understandable enough that I can explain every important component in a technical interview.

5. Autonomous execution rules — important

I want you to work autonomously and avoid unnecessary interruptions.

Follow these rules strictly:

First inspect the existing workspace and available tools.
Make reasonable engineering decisions yourself.
Do not ask me to choose frameworks, filenames, folder structures, implementation details, or minor design decisions.
Do not send a message or request approval for every file you create or every command you run.
Do not repeatedly ask for confirmation to continue.
Do not stop after presenting a plan. Start implementing immediately.
Create and modify project files directly in the workspace.
Run commands, install project dependencies when appropriate, execute tests, and fix failures within the available permissions.
Do not overwrite unrelated existing files or destroy existing work.
If an action requires unavailable credentials, permissions, or an interactive approval, explain the blocker briefly and continue with the parts that do not depend on it.
Never invent test results, successful executions, or capabilities you have not verified.
If a minor decision is unclear, choose a sensible default and document it.
Ask me a question only if a genuinely blocking decision cannot be resolved safely from context.

If the workspace is empty, create the project from scratch. If a suitable project already exists, inspect it and extend it carefully.

6. Implementation workflow

Work through these stages without requiring approval between them:

Inspect the workspace and identify the available runtime, tools, and constraints.
Establish the project architecture and create the initial files.
Implement the offline assistant, evaluation dataset, and test runner.
Implement scoring, reporting, regression detection, and baseline comparison.
Implement adversarial tests and optional LLM judging.
Configure CI and dependency management.
Add documentation, sample results generated by actual runs, and setup instructions.
Run the full offline test suite and linting.
Fix failures and rerun the relevant checks.
Review the final project for security issues, missing features, and misleading claims.

Prioritize a complete, tested vertical slice over a large amount of unfinished code. If time or execution limits become an issue, deliver the working core first and document any remaining limitations.

7. Required deliverables

At completion, provide:

The working project in the current workspace.
A clear README with setup, commands, architecture, example results, and limitations.
At least 40 evaluation cases.
Automated tests and an offline evaluation runner.
A scoring rubric and human-annotated calibration examples.
A regression comparison mechanism.
Adversarial security tests.
A GitHub Actions workflow.
A sample report generated by running the actual implementation.
A concise summary of files created, tests executed, results obtained, and anything still incomplete.

Also include a section called "Technical Interview Guide" explaining the architecture, evaluation methodology, trade-offs, known weaknesses, and possible improvements.

Definition of done

The project is complete only when:

A fresh setup can run the documented offline commands.
Automated tests pass.
The offline evaluation executes real test cases and produces a report.
Regression checks can detect an intentionally introduced failure.
Adversarial tests verify concrete security properties.
Optional live-model features are documented and isolated from offline CI.
The README reflects what was actually implemented and tested.

Start by inspecting the workspace, then implement the project. Do not respond with just a plan or ask me to approve routine decisions.