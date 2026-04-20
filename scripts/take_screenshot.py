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
        ]
    )

    try:
        url = f"http://localhost:{port}"
        with sync_playwright() as p:
            print("Launching browser...")
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            # Wait for streamlit to be ready
            print("Waiting for Streamlit to load...")
            max_retries = 30
            for i in range(max_retries):
                try:
                    page.goto(url)
                    # Streamlit apps take a while to render React components
                    # We wait for the sidebar title or main header
                    page.wait_for_selector("text=Wherewolf", timeout=10000)
                    print("App loaded!")
                    break
                except Exception:
                    print(f"Streamlit not ready yet (attempt {i + 1}/{max_retries})...")
                    time.sleep(2)
            else:
                print("Streamlit failed to load in time.")
                return

            # Let's wait a bit for animations and logo to settle
            print("Settling UI...")
            time.sleep(10)

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
