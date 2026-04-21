from streamlit.testing.v1 import AppTest
from unittest.mock import MagicMock, patch


def test_app_cancel_logic_mocked():
    """Verify that clicking Cancel calls interrupt on the active engine."""
    with patch("wherewolf.app.DuckDBEngine") as mock_engine_cls:
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine

        at = AppTest.from_file("src/wherewolf/app.py")
        at.run()

        # Simulate that a query is running
        at.session_state.is_running = True
        at.session_state.active_engine = mock_engine
        at.run()

        # Find Cancel button
        cancel_btn = next(b for b in at.button if b.label == "🛑 Cancel")
        assert not cancel_btn.disabled

        cancel_btn.click().run()

        # Verify interrupt was called
        mock_engine.interrupt.assert_called_once()
        assert at.session_state.is_running is False
        assert at.session_state.active_engine is None
