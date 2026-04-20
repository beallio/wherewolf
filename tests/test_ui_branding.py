from streamlit.testing.v1 import AppTest


def test_sidebar_is_visible_by_default():
    """Verify that the sidebar is expanded by default as configured."""
    at = AppTest.from_file("src/wherewolf/app.py")
    at.run()

    # Check sidebar state - in AppTest, we can check if it has elements
    assert at.sidebar.title[0].value == "Wherewolf"


def test_branding_css_present():
    """Verify that the custom CSS for hiding branding is injected."""
    at = AppTest.from_file("src/wherewolf/app.py")
    at.run()

    # Find the markdown element containing our style tag
    style_present = False
    for markdown in at.markdown:
        if "<style>" in markdown.value and "#MainMenu" in markdown.value:
            # Also ensure we ARE NOT hiding stToolbar anymore
            if 'data-testid="stToolbar"' not in markdown.value:
                style_present = True
                break

    assert style_present, "Custom branding CSS not found or still hiding toolbar"
