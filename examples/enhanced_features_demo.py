"""Demo script for Enhanced Features: HTML Reports & Smart ID Extraction.

This script demonstrates how to use the new features programmatically.
"""

import schemathesis
from schemathesis.extraction import enable_id_extraction, get_extraction_summary, disable_id_extraction
from schemathesis.reporting import enable_html_report, generate_report, disable_html_report


def demo_html_report():
    """Demonstrate HTML report generation."""
    print("=" * 60)
    print("HTML Report Generation Demo")
    print("=" * 60)

    # Enable HTML report generation
    enable_html_report(
        output_path="./demo-report.html",
        title="Demo API Test Report",
        include_passed_details=True,
        max_body_size=10240,
        api_name="Demo API",
        api_version="1.0.0",
        base_url="https://httpbin.org",
    )

    # Load schema and run tests
    schema = schemathesis.openapi.from_url("https://httpbin.org/spec.json")

    print("Running tests...")
    for operation in schema.get_all_operations():
        print(f"  Testing: {operation.method.upper()} {operation.path}")

        # Generate and execute a few test cases
        for case in operation.as_strategy().example():
            try:
                response = case.call()
                print(f"    Response: {response.status_code}")
            except Exception as e:
                print(f"    Error: {e}")
            break  # Just one example per operation for demo

    # Generate the report
    report_path = generate_report()
    print(f"\n✅ Report generated: {report_path}")

    # Cleanup
    disable_html_report()


def demo_id_extraction():
    """Demonstrate ID extraction and injection."""
    print("\n" + "=" * 60)
    print("ID Extraction Demo")
    print("=" * 60)

    # Enable ID extraction
    enable_id_extraction(
        prefer="latest",
        fallback_to_generated=True,
        inject_into_body=True,
        inject_into_query=True,
        verbose=True,
    )

    # For this demo, we'll use a mock scenario
    print("\nID Extraction is now enabled.")
    print("When running tests, IDs will be automatically:")
    print("  1. Extracted from successful POST/PUT responses")
    print("  2. Stored with resource type context")
    print("  3. Injected into subsequent GET/PUT/DELETE requests")

    # Get summary
    summary = get_extraction_summary()
    print(f"\nExtraction Summary: {summary}")

    # Cleanup
    disable_id_extraction()


def demo_combined():
    """Demonstrate both features together."""
    print("\n" + "=" * 60)
    print("Combined Features Demo")
    print("=" * 60)

    # Enable both features
    enable_html_report(
        output_path="./combined-demo-report.html",
        title="Combined Features Demo Report",
    )

    enable_id_extraction(
        prefer="latest",
        verbose=True,
    )

    print("\nBoth features are now enabled!")
    print("- HTML reports will capture all test data")
    print("- ID extraction will improve test coverage")
    print("- The report will include ID extraction summary")

    # Cleanup
    disable_html_report()
    disable_id_extraction()


if __name__ == "__main__":
    print("Schemathesis Enhanced Features Demo")
    print("====================================\n")

    # Run demos
    try:
        demo_id_extraction()
        demo_combined()
        # demo_html_report()  # Uncomment to run with real API
    except Exception as e:
        print(f"Demo error: {e}")

    print("\n✅ Demo complete!")
