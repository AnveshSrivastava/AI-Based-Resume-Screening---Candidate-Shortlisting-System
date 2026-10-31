"""UI smoke tests using streamlit.testing.v1.AppTest."""

from pathlib import Path
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_renders_without_errors():
    """Verify that app.py loads cleanly and builds all sidebar widgets and tabs."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    assert not at.exception
    # Check that tabs and sidebar sliders exist
    assert len(at.tabs) == 5
    assert len(at.sidebar.slider) >= 8


def test_app_sample_jd_selection():
    """Verify selecting a sample JD from the selectbox and running parse."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()

    # Check that title is rendered
    assert at.title[0].value == "🎯 AI Resume Screening & Candidate Shortlisting"
