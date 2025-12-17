"""Workflow reporting integration with HTML report generator.

Extends the HTML report to include workflow execution results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schemathesis.workflows.models import WorkflowResult, StepResult, StepStatus


class WorkflowReportGenerator:
    """Generates HTML reports for workflow execution results."""

    def __init__(
        self,
        title: str = "Workflow Test Report",
    ) -> None:
        """Initialize the workflow report generator.

        Args:
            title: Title for the report.
        """
        self.title = title

    def generate(
        self,
        workflow_results: list[WorkflowResult],
        output_path: str | Path,
        api_name: str = "",
        base_url: str = "",
    ) -> Path:
        """Generate an HTML report from workflow results.

        Args:
            workflow_results: List of workflow execution results.
            output_path: Path where the HTML file should be written.
            api_name: Name of the API being tested.
            base_url: Base URL of the API.

        Returns:
            Path to the generated report file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build report data
        data = self._build_report_data(workflow_results, api_name, base_url)
        data_json = json.dumps(data, indent=2, default=str)

        # Generate HTML
        html_content = self._generate_html(data, data_json)

        output_path.write_text(html_content, encoding="utf-8")
        return output_path

    def _build_report_data(
        self,
        workflow_results: list[WorkflowResult],
        api_name: str,
        base_url: str,
    ) -> dict[str, Any]:
        """Build the report data structure."""
        total_workflows = len(workflow_results)
        passed_workflows = sum(1 for r in workflow_results if r.status == StepStatus.PASSED)
        failed_workflows = sum(1 for r in workflow_results if r.status == StepStatus.FAILED)
        errored_workflows = sum(1 for r in workflow_results if r.status == StepStatus.ERRORED)

        total_steps = sum(r.total_steps for r in workflow_results)
        passed_steps = sum(r.passed_steps for r in workflow_results)
        failed_steps = sum(r.failed_steps for r in workflow_results)
        skipped_steps = sum(r.skipped_steps for r in workflow_results)

        total_duration = sum(r.duration_seconds for r in workflow_results)

        return {
            "title": self.title,
            "api_name": api_name,
            "base_url": base_url,
            "summary": {
                "total_workflows": total_workflows,
                "passed_workflows": passed_workflows,
                "failed_workflows": failed_workflows,
                "errored_workflows": errored_workflows,
                "total_steps": total_steps,
                "passed_steps": passed_steps,
                "failed_steps": failed_steps,
                "skipped_steps": skipped_steps,
                "total_duration": total_duration,
            },
            "workflows": [r.to_dict() for r in workflow_results],
        }

    def _generate_html(self, data: dict[str, Any], data_json: str) -> str:
        """Generate the complete HTML content."""
        summary = data["summary"]

        # Calculate percentages
        total_wf = summary["total_workflows"]
        passed_wf_pct = (summary["passed_workflows"] / total_wf * 100) if total_wf > 0 else 0
        failed_wf_pct = (summary["failed_workflows"] / total_wf * 100) if total_wf > 0 else 0

        total_steps = summary["total_steps"]
        passed_steps_pct = (summary["passed_steps"] / total_steps * 100) if total_steps > 0 else 0
        failed_steps_pct = (summary["failed_steps"] / total_steps * 100) if total_steps > 0 else 0

        # Generate workflow cards
        workflow_cards = self._generate_workflow_cards(data["workflows"])

        css = self._get_css()
        js = self._get_js()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title}</title>
    <style>
{css}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="header-content">
                <h1>{self.title}</h1>
                <div class="header-meta">
                    <span class="meta-item">
                        <strong>API:</strong> {data.get('api_name', 'Unknown')}
                    </span>
                    <span class="meta-item">
                        <strong>Base URL:</strong> {data.get('base_url', 'N/A')}
                    </span>
                    <span class="meta-item">
                        <strong>Total Duration:</strong> {summary['total_duration']:.2f}s
                    </span>
                </div>
            </div>
        </header>

        <!-- Executive Summary -->
        <section class="summary-section">
            <h2>Executive Summary</h2>
            <div class="summary-row">
                <div class="summary-group">
                    <h3>Workflows</h3>
                    <div class="summary-grid">
                        <div class="summary-card total">
                            <div class="summary-number">{summary['total_workflows']}</div>
                            <div class="summary-label">Total</div>
                        </div>
                        <div class="summary-card passed">
                            <div class="summary-number">{summary['passed_workflows']}</div>
                            <div class="summary-label">Passed ({passed_wf_pct:.0f}%)</div>
                        </div>
                        <div class="summary-card failed">
                            <div class="summary-number">{summary['failed_workflows']}</div>
                            <div class="summary-label">Failed ({failed_wf_pct:.0f}%)</div>
                        </div>
                    </div>
                </div>
                <div class="summary-group">
                    <h3>Steps</h3>
                    <div class="summary-grid">
                        <div class="summary-card total">
                            <div class="summary-number">{summary['total_steps']}</div>
                            <div class="summary-label">Total</div>
                        </div>
                        <div class="summary-card passed">
                            <div class="summary-number">{summary['passed_steps']}</div>
                            <div class="summary-label">Passed ({passed_steps_pct:.0f}%)</div>
                        </div>
                        <div class="summary-card failed">
                            <div class="summary-number">{summary['failed_steps']}</div>
                            <div class="summary-label">Failed ({failed_steps_pct:.0f}%)</div>
                        </div>
                        <div class="summary-card skipped">
                            <div class="summary-number">{summary['skipped_steps']}</div>
                            <div class="summary-label">Skipped</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="progress-bar">
                <div class="progress-passed" style="width: {passed_wf_pct}%"></div>
                <div class="progress-failed" style="width: {failed_wf_pct}%"></div>
            </div>
        </section>

        <!-- Workflow Results -->
        <section class="workflows-section">
            <h2>Workflow Results</h2>
            <div class="workflows-list">
                {workflow_cards}
            </div>
        </section>

        <!-- Footer -->
        <footer class="footer">
            <p>Generated by Schemathesis Workflow Engine</p>
        </footer>
    </div>

    <script>
        const reportData = {data_json};
        {js}
    </script>
</body>
</html>"""
        return html

    def _generate_workflow_cards(self, workflows: list[dict[str, Any]]) -> str:
        """Generate HTML cards for each workflow."""
        cards = []

        for workflow in workflows:
            status = workflow["status"]
            status_class = status.lower()

            # Generate step timeline
            all_steps = (
                workflow.get("setup_results", []) +
                workflow.get("step_results", []) +
                workflow.get("teardown_results", [])
            )
            timeline_html = self._generate_step_timeline(all_steps)

            # Generate step details
            steps_html = self._generate_step_details(all_steps)

            # Generate extracted variables
            variables_html = ""
            if workflow.get("variables"):
                variables_html = f"""
                <div class="variables-section">
                    <h4>Extracted Variables</h4>
                    <pre class="variables-pre">{json.dumps(workflow['variables'], indent=2, default=str)}</pre>
                </div>
                """

            error_html = ""
            if workflow.get("error_message"):
                error_html = f"""
                <div class="error-message">
                    <strong>Error:</strong> {workflow['error_message']}
                </div>
                """

            cards.append(f"""
            <div class="workflow-card status-{status_class}">
                <div class="workflow-header" onclick="toggleWorkflow(this)">
                    <div class="workflow-title">
                        <span class="status-indicator status-{status_class}"></span>
                        <span class="workflow-name">{workflow['workflow_name']}</span>
                    </div>
                    <div class="workflow-meta">
                        <span class="workflow-stats">
                            {workflow['passed_steps']} passed / {workflow['failed_steps']} failed / {workflow['skipped_steps']} skipped
                        </span>
                        <span class="workflow-duration">{workflow['duration_seconds']:.2f}s</span>
                        <span class="status-badge status-{status_class}">{status.upper()}</span>
                        <span class="expand-icon">▼</span>
                    </div>
                </div>
                <div class="workflow-details" style="display: none;">
                    {error_html}
                    <div class="timeline-section">
                        <h4>Step Timeline</h4>
                        <div class="step-timeline">
                            {timeline_html}
                        </div>
                    </div>
                    <div class="steps-section">
                        <h4>Step Details</h4>
                        {steps_html}
                    </div>
                    {variables_html}
                </div>
            </div>
            """)

        return "\n".join(cards) if cards else "<p>No workflows executed</p>"

    def _generate_step_timeline(self, steps: list[dict[str, Any]]) -> str:
        """Generate a visual timeline of steps."""
        items = []
        for step in steps:
            status = step.get("status", "pending")
            status_class = status.lower()
            items.append(f"""
            <div class="timeline-item status-{status_class}" title="{step['step_name']}: {status}">
                <div class="timeline-dot"></div>
                <div class="timeline-label">{step['step_name']}</div>
            </div>
            """)
        return "\n".join(items)

    def _generate_step_details(self, steps: list[dict[str, Any]]) -> str:
        """Generate detailed view of each step."""
        items = []
        for step in steps:
            status = step.get("status", "pending")
            status_class = status.lower()

            request = step.get("request", {})
            response = step.get("response", {})

            request_html = ""
            if request.get("method"):
                request_html = f"""
                <div class="step-request">
                    <strong>Request:</strong> {request.get('method', '')} {request.get('url', '')}
                </div>
                """

            response_html = ""
            if response.get("status"):
                response_html = f"""
                <div class="step-response">
                    <strong>Response:</strong> {response.get('status', '')} ({response.get('response_time_ms', 0):.0f}ms)
                </div>
                """

            error_html = ""
            if step.get("error_message"):
                error_html = f"""
                <div class="step-error">
                    <strong>Error:</strong> {step['error_message']}
                </div>
                """

            extracted_html = ""
            if step.get("extracted_data"):
                extracted_html = f"""
                <div class="step-extracted">
                    <strong>Extracted:</strong> {json.dumps(step['extracted_data'], default=str)}
                </div>
                """

            items.append(f"""
            <div class="step-detail status-{status_class}">
                <div class="step-header" onclick="toggleStep(this)">
                    <span class="status-dot status-{status_class}"></span>
                    <span class="step-name">{step['step_name']}</span>
                    <span class="step-duration">{step.get('duration_ms', 0):.0f}ms</span>
                    <span class="expand-icon">▶</span>
                </div>
                <div class="step-body" style="display: none;">
                    {request_html}
                    {response_html}
                    {error_html}
                    {extracted_html}
                </div>
            </div>
            """)

        return "\n".join(items) if items else "<p>No steps executed</p>"

    def _get_css(self) -> str:
        """Get the embedded CSS styles."""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 24px;
        }

        .header h1 {
            font-size: 28px;
            margin-bottom: 12px;
        }

        .header-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            font-size: 14px;
            opacity: 0.9;
        }

        .summary-section, .workflows-section {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        h2 {
            font-size: 20px;
            margin-bottom: 20px;
            color: #2d3748;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 10px;
        }

        .summary-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 20px;
        }

        @media (max-width: 768px) {
            .summary-row {
                grid-template-columns: 1fr;
            }
        }

        .summary-group h3 {
            font-size: 16px;
            margin-bottom: 12px;
            color: #4a5568;
        }

        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 12px;
        }

        .summary-card {
            padding: 16px;
            border-radius: 8px;
            text-align: center;
        }

        .summary-card.total { background: #e2e8f0; }
        .summary-card.passed { background: #c6f6d5; }
        .summary-card.failed { background: #fed7d7; }
        .summary-card.skipped { background: #e9d8fd; }

        .summary-number {
            font-size: 28px;
            font-weight: 700;
        }

        .summary-label {
            font-size: 12px;
            color: #4a5568;
        }

        .progress-bar {
            height: 10px;
            background: #e2e8f0;
            border-radius: 5px;
            overflow: hidden;
            display: flex;
        }

        .progress-passed { background: #48bb78; }
        .progress-failed { background: #f56565; }

        .workflow-card {
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            margin-bottom: 16px;
            overflow: hidden;
        }

        .workflow-card.status-passed { border-left: 4px solid #48bb78; }
        .workflow-card.status-failed { border-left: 4px solid #f56565; }
        .workflow-card.status-errored { border-left: 4px solid #ed8936; }

        .workflow-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            background: #f7fafc;
            cursor: pointer;
        }

        .workflow-header:hover {
            background: #edf2f7;
        }

        .workflow-title {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }

        .status-indicator.status-passed { background: #48bb78; }
        .status-indicator.status-failed { background: #f56565; }
        .status-indicator.status-errored { background: #ed8936; }
        .status-indicator.status-skipped { background: #a0aec0; }

        .workflow-name {
            font-weight: 600;
            font-size: 16px;
        }

        .workflow-meta {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .workflow-stats {
            font-size: 13px;
            color: #718096;
        }

        .workflow-duration {
            font-size: 13px;
            color: #718096;
        }

        .status-badge {
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }

        .status-badge.status-passed { background: #c6f6d5; color: #22543d; }
        .status-badge.status-failed { background: #fed7d7; color: #742a2a; }
        .status-badge.status-errored { background: #feebc8; color: #744210; }
        .status-badge.status-skipped { background: #e9d8fd; color: #553c9a; }

        .expand-icon {
            color: #a0aec0;
            transition: transform 0.2s;
        }

        .workflow-details {
            padding: 20px;
            border-top: 1px solid #e2e8f0;
        }

        .error-message {
            background: #fff5f5;
            border: 1px solid #fc8181;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 16px;
            color: #c53030;
        }

        .timeline-section, .steps-section, .variables-section {
            margin-bottom: 20px;
        }

        .timeline-section h4, .steps-section h4, .variables-section h4 {
            font-size: 14px;
            margin-bottom: 12px;
            color: #4a5568;
        }

        .step-timeline {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .timeline-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 8px;
            min-width: 80px;
        }

        .timeline-dot {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-bottom: 4px;
        }

        .timeline-item.status-passed .timeline-dot { background: #48bb78; }
        .timeline-item.status-failed .timeline-dot { background: #f56565; }
        .timeline-item.status-errored .timeline-dot { background: #ed8936; }
        .timeline-item.status-skipped .timeline-dot { background: #a0aec0; }
        .timeline-item.status-pending .timeline-dot { background: #e2e8f0; }

        .timeline-label {
            font-size: 11px;
            color: #718096;
            text-align: center;
            max-width: 80px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .step-detail {
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            margin-bottom: 8px;
        }

        .step-header {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 14px;
            cursor: pointer;
            background: #f7fafc;
        }

        .step-header:hover {
            background: #edf2f7;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }

        .status-dot.status-passed { background: #48bb78; }
        .status-dot.status-failed { background: #f56565; }
        .status-dot.status-errored { background: #ed8936; }
        .status-dot.status-skipped { background: #a0aec0; }

        .step-name {
            flex: 1;
            font-weight: 500;
        }

        .step-duration {
            font-size: 12px;
            color: #718096;
        }

        .step-body {
            padding: 12px 14px;
            font-size: 13px;
            border-top: 1px solid #e2e8f0;
        }

        .step-request, .step-response, .step-error, .step-extracted {
            margin-bottom: 8px;
        }

        .step-error {
            color: #c53030;
        }

        .variables-pre {
            background: #1a202c;
            color: #e2e8f0;
            padding: 12px;
            border-radius: 6px;
            font-size: 12px;
            overflow-x: auto;
        }

        .footer {
            text-align: center;
            padding: 20px;
            color: #718096;
            font-size: 14px;
        }
        """

    def _get_js(self) -> str:
        """Get the embedded JavaScript."""
        return """
        function toggleWorkflow(header) {
            const details = header.nextElementSibling;
            const icon = header.querySelector('.expand-icon');
            if (details.style.display === 'none') {
                details.style.display = 'block';
                icon.textContent = '▲';
            } else {
                details.style.display = 'none';
                icon.textContent = '▼';
            }
        }

        function toggleStep(header) {
            const body = header.nextElementSibling;
            const icon = header.querySelector('.expand-icon');
            if (body.style.display === 'none') {
                body.style.display = 'block';
                icon.textContent = '▼';
            } else {
                body.style.display = 'none';
                icon.textContent = '▶';
            }
        }
        """


def generate_workflow_report(
    workflow_results: list[WorkflowResult],
    output_path: str | Path,
    title: str = "Workflow Test Report",
    api_name: str = "",
    base_url: str = "",
) -> Path:
    """Convenience function to generate a workflow report.

    Args:
        workflow_results: List of workflow execution results.
        output_path: Path where the HTML file should be written.
        title: Title for the report.
        api_name: Name of the API being tested.
        base_url: Base URL of the API.

    Returns:
        Path to the generated report file.
    """
    generator = WorkflowReportGenerator(title=title)
    return generator.generate(workflow_results, output_path, api_name, base_url)
