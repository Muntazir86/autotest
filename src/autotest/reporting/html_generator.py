"""HTML Report Generator for Autotest.

Generates self-contained, interactive HTML reports from test run data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autotest.reporting.models import TestRunInfo


class HTMLReportGenerator:
    """Generates self-contained HTML reports from test run data."""

    def __init__(
        self,
        title: str = "API Test Report",
        include_passed_details: bool = False,
    ) -> None:
        """Initialize the HTML report generator.

        Args:
            title: Title for the report.
            include_passed_details: Whether to include full details for passed tests.
        """
        self.title = title
        self.include_passed_details = include_passed_details

    def generate(self, run_info: TestRunInfo, output_path: str | Path) -> Path:
        """Generate an HTML report from test run data.

        Args:
            run_info: The test run information to include in the report.
            output_path: Path where the HTML file should be written.

        Returns:
            Path to the generated report file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert run info to JSON for embedding
        data = run_info.to_dict()
        data_json = json.dumps(data, indent=2, default=str)

        # Generate the HTML content
        html_content = self._generate_html(data, data_json)

        # Write the file
        output_path.write_text(html_content, encoding="utf-8")
        return output_path

    def _generate_html(self, data: dict, data_json: str) -> str:
        """Generate the complete HTML content."""
        css = self._get_css()
        js = self._get_js()

        # Calculate summary stats
        total = data["total_tests"]
        passed = data["passed"]
        failed = data["failed"]
        errored = data["errored"]
        skipped = data["skipped"]

        passed_pct = (passed / total * 100) if total > 0 else 0
        failed_pct = (failed / total * 100) if total > 0 else 0
        errored_pct = (errored / total * 100) if total > 0 else 0

        # Generate endpoint rows
        endpoint_rows = self._generate_endpoint_rows(data["endpoints"])

        # Generate failed tests section
        failed_tests_html = self._generate_failed_tests(data["test_results"])

        # Generate all tests section
        all_tests_html = self._generate_all_tests(data["test_results"])

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
                        <strong>API:</strong> {data.get('api_name', 'Unknown')} {data.get('api_version', '')}
                    </span>
                    <span class="meta-item">
                        <strong>Base URL:</strong> {data.get('base_url', 'N/A')}
                    </span>
                    <span class="meta-item">
                        <strong>Run Time:</strong> {data.get('start_time', 'N/A')}
                    </span>
                    <span class="meta-item">
                        <strong>Duration:</strong> {data.get('duration_seconds', 0):.2f}s
                    </span>
                </div>
            </div>
        </header>

        <!-- Executive Summary -->
        <section class="summary-section">
            <h2>Executive Summary</h2>
            <div class="summary-grid">
                <div class="summary-card total">
                    <div class="summary-number">{total}</div>
                    <div class="summary-label">Total Tests</div>
                </div>
                <div class="summary-card passed">
                    <div class="summary-number">{passed}</div>
                    <div class="summary-label">Passed ({passed_pct:.1f}%)</div>
                </div>
                <div class="summary-card failed">
                    <div class="summary-number">{failed}</div>
                    <div class="summary-label">Failed ({failed_pct:.1f}%)</div>
                </div>
                <div class="summary-card errored">
                    <div class="summary-number">{errored}</div>
                    <div class="summary-label">Errors ({errored_pct:.1f}%)</div>
                </div>
                <div class="summary-card skipped">
                    <div class="summary-number">{skipped}</div>
                    <div class="summary-label">Skipped</div>
                </div>
            </div>
            <div class="progress-bar">
                <div class="progress-passed" style="width: {passed_pct}%"></div>
                <div class="progress-failed" style="width: {failed_pct}%"></div>
                <div class="progress-errored" style="width: {errored_pct}%"></div>
            </div>
        </section>

        <!-- Endpoints Overview -->
        <section class="endpoints-section">
            <h2>Endpoints Overview</h2>
            <div class="table-container">
                <table class="endpoints-table">
                    <thead>
                        <tr>
                            <th>Method</th>
                            <th>Path</th>
                            <th>Total</th>
                            <th>Passed</th>
                            <th>Failed</th>
                            <th>Avg Time (ms)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {endpoint_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Failed Tests -->
        <section class="failed-section">
            <h2>Failed Tests ({failed + errored})</h2>
            <div class="failed-tests">
                {failed_tests_html if failed + errored > 0 else '<p class="no-failures">No failures! All tests passed.</p>'}
            </div>
        </section>

        <!-- All Tests -->
        <section class="all-tests-section">
            <h2>All Tests</h2>
            <div class="filters">
                <input type="text" id="searchInput" placeholder="Search tests..." class="search-input">
                <select id="statusFilter" class="filter-select">
                    <option value="">All Statuses</option>
                    <option value="passed">Passed</option>
                    <option value="failed">Failed</option>
                    <option value="errored">Errored</option>
                    <option value="skipped">Skipped</option>
                </select>
                <select id="methodFilter" class="filter-select">
                    <option value="">All Methods</option>
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="PATCH">PATCH</option>
                    <option value="DELETE">DELETE</option>
                </select>
            </div>
            <div class="all-tests" id="allTests">
                {all_tests_html}
            </div>
        </section>

        <!-- Footer -->
        <footer class="footer">
            <p>Generated by Autotest v{data.get('AUTOTEST_VERSION', 'unknown')}</p>
            <p>Report generated at {data.get('end_time', 'N/A')}</p>
        </footer>
    </div>

    <script>
        const reportData = {data_json};
        {js}
    </script>
</body>
</html>"""
        return html

    def _generate_endpoint_rows(self, endpoints: dict) -> str:
        """Generate HTML rows for the endpoints table."""
        rows = []
        for key, ep in sorted(endpoints.items()):
            method_class = ep["method"].lower()
            status_class = "success" if ep["failed"] == 0 else "failure"
            rows.append(f"""
                <tr class="{status_class}">
                    <td><span class="method-badge method-{method_class}">{ep['method']}</span></td>
                    <td class="path-cell">{ep['path']}</td>
                    <td>{ep['total_tests']}</td>
                    <td class="passed-cell">{ep['passed']}</td>
                    <td class="failed-cell">{ep['failed']}</td>
                    <td>{ep['avg_response_time_ms']:.2f}</td>
                </tr>
            """)
        return "\n".join(rows) if rows else "<tr><td colspan='6'>No endpoints tested</td></tr>"

    def _generate_failed_tests(self, test_results: list) -> str:
        """Generate HTML for failed tests section."""
        failed = [t for t in test_results if t["status"] in ("failed", "errored")]
        if not failed:
            return ""

        items = []
        for test in failed:
            request = test["request"]
            response = test["response"]
            method_class = request["method"].lower()

            # Format request/response bodies
            req_body = self._format_json(request.get("body"))
            resp_body = self._format_json(response.get("body"))

            # Format check results
            checks_html = ""
            for check in test.get("check_results", []):
                check_status = "✓" if check["status"] == "passed" else "✗"
                check_class = "check-passed" if check["status"] == "passed" else "check-failed"
                checks_html += f'<div class="{check_class}">{check_status} {check["name"]}'
                if check.get("message"):
                    checks_html += f': {check["message"]}'
                checks_html += "</div>"

            curl_html = ""
            if test.get("curl_command"):
                curl_html = f"""
                <div class="curl-section">
                    <div class="curl-header">
                        <strong>cURL Command</strong>
                        <button class="copy-btn" onclick="copyToClipboard(this, `{self._escape_js(test['curl_command'])}`)">Copy</button>
                    </div>
                    <pre class="curl-command">{test['curl_command']}</pre>
                </div>
                """

            items.append(f"""
            <div class="test-card failed-card">
                <div class="test-header" onclick="toggleDetails(this)">
                    <span class="method-badge method-{method_class}">{request['method']}</span>
                    <span class="test-path">{request['path']}</span>
                    <span class="status-badge status-{test['status']}">{test['status'].upper()}</span>
                    <span class="response-code">{response['status_code']}</span>
                    <span class="expand-icon">▼</span>
                </div>
                <div class="test-details" style="display: none;">
                    <div class="failure-reason">
                        <strong>Failure Reason:</strong> {test.get('failure_reason', 'Unknown')}
                    </div>
                    <div class="checks-section">
                        <strong>Check Results:</strong>
                        {checks_html}
                    </div>
                    <div class="request-response">
                        <div class="request-section">
                            <h4>Request</h4>
                            <div class="detail-item"><strong>URL:</strong> {request['url']}</div>
                            <div class="detail-item"><strong>Headers:</strong></div>
                            <pre class="headers-pre">{self._format_json(request.get('headers', {{}}))}</pre>
                            <div class="detail-item"><strong>Body:</strong></div>
                            <pre class="body-pre">{req_body}</pre>
                        </div>
                        <div class="response-section">
                            <h4>Response ({response['response_time_ms']:.2f}ms)</h4>
                            <div class="detail-item"><strong>Status:</strong> {response['status_code']} {response['status_text']}</div>
                            <div class="detail-item"><strong>Headers:</strong></div>
                            <pre class="headers-pre">{self._format_json(response.get('headers', {{}}))}</pre>
                            <div class="detail-item"><strong>Body:</strong></div>
                            <pre class="body-pre">{resp_body}</pre>
                        </div>
                    </div>
                    {curl_html}
                </div>
            </div>
            """)
        return "\n".join(items)

    def _generate_all_tests(self, test_results: list) -> str:
        """Generate HTML for all tests section."""
        items = []
        for test in test_results:
            request = test["request"]
            response = test["response"]
            method_class = request["method"].lower()
            status = test["status"]

            items.append(f"""
            <div class="test-row" data-status="{status}" data-method="{request['method']}" data-path="{request['path']}">
                <div class="test-header-compact" onclick="toggleDetails(this)">
                    <span class="method-badge method-{method_class}">{request['method']}</span>
                    <span class="test-path">{request['path']}</span>
                    <span class="status-badge status-{status}">{status.upper()}</span>
                    <span class="response-code">{response['status_code']}</span>
                    <span class="response-time">{response['response_time_ms']:.0f}ms</span>
                    <span class="expand-icon">▶</span>
                </div>
                <div class="test-details-compact" style="display: none;">
                    <div class="detail-grid">
                        <div class="detail-col">
                            <strong>Request URL:</strong> {request['url']}<br>
                            <strong>Phase:</strong> {test.get('test_phase', 'N/A')}<br>
                            <strong>Operation ID:</strong> {test.get('operation_id', 'N/A')}
                        </div>
                    </div>
                </div>
            </div>
            """)
        return "\n".join(items) if items else "<p>No tests recorded</p>"

    def _format_json(self, data) -> str:
        """Format data as JSON for display."""
        if data is None:
            return "null"
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                return json.dumps(parsed, indent=2)
            except (json.JSONDecodeError, TypeError):
                return data
        try:
            return json.dumps(data, indent=2, default=str)
        except (TypeError, ValueError):
            return str(data)

    def _escape_js(self, s: str) -> str:
        """Escape a string for use in JavaScript."""
        return s.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    def _get_css(self) -> str:
        """Get the embedded CSS styles."""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
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

        .summary-section, .endpoints-section, .failed-section, .all-tests-section {
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

        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }

        .summary-card {
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }

        .summary-card.total { background: #e2e8f0; }
        .summary-card.passed { background: #c6f6d5; }
        .summary-card.failed { background: #fed7d7; }
        .summary-card.errored { background: #feebc8; }
        .summary-card.skipped { background: #e9d8fd; }

        .summary-number {
            font-size: 36px;
            font-weight: 700;
        }

        .summary-label {
            font-size: 14px;
            color: #4a5568;
            margin-top: 4px;
        }

        .progress-bar {
            height: 12px;
            background: #e2e8f0;
            border-radius: 6px;
            overflow: hidden;
            display: flex;
        }

        .progress-passed { background: #48bb78; }
        .progress-failed { background: #f56565; }
        .progress-errored { background: #ed8936; }

        .table-container {
            overflow-x: auto;
        }

        .endpoints-table {
            width: 100%;
            border-collapse: collapse;
        }

        .endpoints-table th, .endpoints-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }

        .endpoints-table th {
            background: #f7fafc;
            font-weight: 600;
            color: #4a5568;
        }

        .endpoints-table tr:hover {
            background: #f7fafc;
        }

        .method-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .method-get { background: #c6f6d5; color: #22543d; }
        .method-post { background: #bee3f8; color: #2a4365; }
        .method-put { background: #feebc8; color: #744210; }
        .method-patch { background: #e9d8fd; color: #553c9a; }
        .method-delete { background: #fed7d7; color: #742a2a; }

        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }

        .status-passed { background: #c6f6d5; color: #22543d; }
        .status-failed { background: #fed7d7; color: #742a2a; }
        .status-errored { background: #feebc8; color: #744210; }
        .status-skipped { background: #e9d8fd; color: #553c9a; }

        .passed-cell { color: #22543d; }
        .failed-cell { color: #c53030; font-weight: 600; }

        .no-failures {
            text-align: center;
            padding: 40px;
            color: #48bb78;
            font-size: 18px;
        }

        .test-card, .test-row {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-bottom: 12px;
            overflow: hidden;
        }

        .failed-card {
            border-color: #fc8181;
        }

        .test-header, .test-header-compact {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px;
            background: #f7fafc;
            cursor: pointer;
            transition: background 0.2s;
        }

        .test-header:hover, .test-header-compact:hover {
            background: #edf2f7;
        }

        .test-path {
            flex: 1;
            font-family: monospace;
            font-size: 14px;
        }

        .response-code {
            font-family: monospace;
            font-weight: 600;
        }

        .response-time {
            color: #718096;
            font-size: 13px;
        }

        .expand-icon {
            color: #a0aec0;
            transition: transform 0.2s;
        }

        .test-details, .test-details-compact {
            padding: 20px;
            background: white;
            border-top: 1px solid #e2e8f0;
        }

        .failure-reason {
            background: #fff5f5;
            border: 1px solid #fc8181;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 16px;
            color: #c53030;
        }

        .checks-section {
            margin-bottom: 16px;
        }

        .check-passed { color: #22543d; }
        .check-failed { color: #c53030; }

        .request-response {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        @media (max-width: 768px) {
            .request-response {
                grid-template-columns: 1fr;
            }
        }

        .request-section, .response-section {
            background: #f7fafc;
            padding: 16px;
            border-radius: 8px;
        }

        .request-section h4, .response-section h4 {
            margin-bottom: 12px;
            color: #2d3748;
        }

        .detail-item {
            margin-bottom: 8px;
            font-size: 14px;
        }

        pre {
            background: #1a202c;
            color: #e2e8f0;
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 12px;
            margin-top: 8px;
        }

        .curl-section {
            margin-top: 16px;
        }

        .curl-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .copy-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }

        .copy-btn:hover {
            background: #5a67d8;
        }

        .filters {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }

        .search-input, .filter-select {
            padding: 10px 14px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            font-size: 14px;
        }

        .search-input {
            flex: 1;
            min-width: 200px;
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
        function toggleDetails(header) {
            const details = header.nextElementSibling;
            const icon = header.querySelector('.expand-icon');
            if (details.style.display === 'none') {
                details.style.display = 'block';
                icon.textContent = '▼';
            } else {
                details.style.display = 'none';
                icon.textContent = '▶';
            }
        }

        function copyToClipboard(btn, text) {
            navigator.clipboard.writeText(text).then(() => {
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(() => {
                    btn.textContent = originalText;
                }, 2000);
            });
        }

        // Filtering functionality
        document.getElementById('searchInput')?.addEventListener('input', filterTests);
        document.getElementById('statusFilter')?.addEventListener('change', filterTests);
        document.getElementById('methodFilter')?.addEventListener('change', filterTests);

        function filterTests() {
            const search = document.getElementById('searchInput')?.value.toLowerCase() || '';
            const status = document.getElementById('statusFilter')?.value || '';
            const method = document.getElementById('methodFilter')?.value || '';

            document.querySelectorAll('.test-row').forEach(row => {
                const rowStatus = row.dataset.status;
                const rowMethod = row.dataset.method;
                const rowPath = row.dataset.path.toLowerCase();

                const matchesSearch = !search || rowPath.includes(search);
                const matchesStatus = !status || rowStatus === status;
                const matchesMethod = !method || rowMethod === method;

                row.style.display = matchesSearch && matchesStatus && matchesMethod ? 'block' : 'none';
            });
        }
        """
