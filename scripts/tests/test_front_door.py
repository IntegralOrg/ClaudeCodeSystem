from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD = "https://github.com/IntegralOrg/ClaudeCodeSystem/archive/refs/heads/main.zip"


def test_index_html_downloads_first_and_keeps_the_cloud_path():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert DOWNLOAD in html and "claude.com/download" in html
    assert html.index(DOWNLOAD) < html.index("github.com/new?template_owner=IntegralOrg")
    for needle in ("Extract All", "Code", "Trust", "send any message", "Mac", "Windows", "No computer"):
        assert needle in html, needle
    assert "GitHub Desktop" not in html.split("No computer")[0]
    assert "—" not in html and "<title>" in html and "prefers-color-scheme" in html


def test_readme_get_started_is_three_steps_with_the_cloud_alternative():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    block = text.split("## Get Started")[1].split("## ")[0]
    assert "1." in block and "2." in block and "3." in block and "4." not in block
    assert DOWNLOAD in block and "Trust" in block and "Max" in block
    assert "Use this template" in block and "claude.ai/code" in block      # the no-computer path


def test_windows_extract_all_names_the_inner_folder():
    for rel in ("README.md", "docs/index.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "ClaudeCodeSystem-main" in text and "inside it" in text, rel
