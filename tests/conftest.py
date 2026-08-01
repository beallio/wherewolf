import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_sessionstart(session):
    cov_plugin = session.config.pluginmanager.get_plugin("_cov")
    if cov_plugin and hasattr(cov_plugin, "cov_controller") and cov_plugin.cov_controller:
        cov = cov_plugin.cov_controller.cov
        if cov and hasattr(cov, "config"):
            print(f"\n[PYTEST-COV] ACTIVE COVERAGE TIMID = {cov.config.timid}", flush=True)
