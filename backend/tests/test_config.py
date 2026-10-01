from app.core.config import BACKEND_DIR, PROJECT_DIR, Settings


def test_blank_path_settings_fall_back_to_project_defaults():
    settings = Settings(crawler_dir="", contracts_dir="")

    assert settings.crawler_dir == PROJECT_DIR / "crawler"
    assert settings.sites_dir == PROJECT_DIR / "crawler" / "sites"
    assert settings.contracts_dir == BACKEND_DIR / "contracts"
    assert settings.schemas_dir == BACKEND_DIR / "contracts" / "schemas"


def test_whitespace_path_settings_also_use_defaults():
    settings = Settings(crawler_dir="   ", contracts_dir="\t")

    assert settings.crawler_dir == PROJECT_DIR / "crawler"
    assert settings.contracts_dir == BACKEND_DIR / "contracts"
