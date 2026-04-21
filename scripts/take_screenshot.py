import time
import subprocess
import os
from playwright.sync_api import sync_playwright


def take_screenshot(output_path):
    # Ensure asset directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Start streamlit in background
    # We use a non-standard port to avoid collisions
    port = 8599
    print(f"Starting Streamlit on port {port}...")
    # Force dark mode via theme.base
    proc = subprocess.Popen(
        [
            "./run.sh",
            "uv",
            "run",
            "streamlit",
            "run",
            "src/wherewolf/app.py",
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--theme.base",
            "dark",
        ]
    )

    try:
        url = f"http://localhost:{port}"
        with sync_playwright() as p:
            print("Launching browser...")
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1200})

            # Wait for streamlit to be ready
            print("Waiting for Streamlit to load...")
            max_retries = 30
            for i in range(max_retries):
                try:
                    page.goto(url, timeout=30000)
                    # Use a selector that only appears when app is rendered
                    page.wait_for_selector("text=Wherewolf", timeout=10000)
                    print("App loaded!")
                    break
                except Exception:
                    print(f"Streamlit not ready yet (attempt {i + 1}/30)...")
                time.sleep(2)
            else:
                print("Streamlit failed to load in time.")
                return

            # Click the "Run" button
            print("Clicking Run...")
            try:
                # Use a specific selector for the primary button
                page.wait_for_selector("text=Run", timeout=20000)
                # Try to click the button by its label
                page.click("button:has-text('Run')")
                print("Clicked Run!")
            except Exception as e:
                print(f"Failed to click Run: {e}")
                # Fallback: try to find any button with Run text
                try:
                    page.get_by_role("button", name="Run").click()
                    print("Clicked Run (fallback)!")
                except Exception as e2:
                    print(f"Double failure on Run button: {e2}")

            # Wait for results to appear (metric or dataframe)
            print("Waiting for results...")
            try:
                page.wait_for_selector("text=Rows Returned", timeout=30000)
                print("Results appeared!")
            except Exception as e:
                print(f"Results did not appear: {e}")

            # Settle UI
            time.sleep(5)

            print(f"Capturing screenshot to {output_path}...")
            page.screenshot(path=output_path)
            browser.close()
            print("Done!")

    finally:
        print("Terminating Streamlit...")
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    take_screenshot("src/wherewolf/assets/img/screenshot.png")
