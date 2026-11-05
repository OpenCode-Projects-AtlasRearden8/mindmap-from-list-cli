"""Offline end-to-end tests for the CLI."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from mindmap_from_list import cli

SAMPLE = "# Study Plan\n## Week one\n- read chapter 1\n- try the examples\n"


@pytest.fixture()
def sample_file(tmp_path):
    path = tmp_path / "input.md"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def run_cli(argv):
    return cli.main(argv)


class TestFileOutputs:
    def test_default_svg_output_name(self, tmp_path, sample_file, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert run_cli([str(sample_file)]) == 0
        out = tmp_path / "input.svg"
        assert out.exists() and out.read_text().lstrip().startswith("<svg")

    def test_pdf_alongside(self, tmp_path, sample_file, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pdf = tmp_path / "out.pdf"
        assert run_cli([str(sample_file), "--pdf", str(pdf)]) == 0
        data = pdf.read_bytes()
        assert data.startswith(b"%PDF") and b"%%EOF" in data[-16:]
        svg = tmp_path / "input.svg"
        assert svg.exists() and svg.read_text().lstrip().startswith("<svg")

    def test_max_depth_flag(self, tmp_path, sample_file):
        svg = tmp_path / "d2.svg"
        code = run_cli([str(sample_file), "-o", str(svg), "--max-depth", "2"])
        assert code == 0
        svg2 = tmp_path / "d1.svg"
        run_cli([str(sample_file), "-o", str(svg2), "--max-depth", "1"])
        assert len(svg2.read_text()) < len(svg.read_text())

    def test_per_branch_flag_changes_output(self, tmp_path, sample_file):
        svg = tmp_path / "a.svg"
        svgb = tmp_path / "b.svg"
        run_cli([str(sample_file), "-o", str(svg)])
        run_cli([str(sample_file), "-o", str(svgb), "--per-branch-colors"])
        assert svg.read_text() != svgb.read_text()

    def test_paper_flag(self, tmp_path, sample_file, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pdf = tmp_path / "letter.pdf"
        assert run_cli([str(sample_file), "--pdf", str(pdf),
                        "--paper", "letter"]) == 0
        assert pdf.stat().st_size > 500

    def test_stdout_mode(self, sample_file):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = run_cli([str(sample_file), "--stdout"])
        assert code == 0
        assert buf.getvalue().lstrip().startswith("<svg")

    def test_bad_palette_fails_cleanly(self, sample_file):
        with pytest.raises(SystemExit):
            run_cli([str(sample_file), "--palette", "no-such"])

    def test_bad_maxdepth_fails_cleanly(self, sample_file, capsys):
        code = run_cli([str(sample_file), "--max-depth", "-3"])
        assert code == 1
        err = capsys.readouterr().err
        assert "max-depth" in err

    def test_missing_input_reports_error(self, capsys):
        code = run_cli(["/nonexistent/file.md"])
        assert code == 1
        assert "cannot read input" in capsys.readouterr().err


class _MockLLM(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence test server noise
        pass

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        reply = {"choices": [{"message": {"content":
                 "1. What happens in week one?\n"
                 "- Recall the two example tasks\n"}}]}
        response = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class TestOptionalQuestions:
    @pytest.fixture()
    def endpoint(self):
        server = HTTPServer(("127.0.0.1", 0), _MockLLM)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{server.server_port}/v1"
        server.shutdown()

    def test_questions_opt_in(self, tmp_path, sample_file, endpoint):
        qfile = tmp_path / "out.questions.txt"
        code = run_cli([str(sample_file), "-o", str(tmp_path / "out.svg"),
                        "--questions", "--endpoint", endpoint])
        assert code == 0
        text = qfile.read_text(encoding="utf-8")
        assert "Week one" in text
        assert "What happens in week one?" in text

    def test_unreachable_endpoint_is_not_fatal(self, tmp_path, sample_file):
        # port 1 is closed; CLI should warn but still write the map
        code = run_cli([str(sample_file), "-o", str(tmp_path / "out.svg"),
                        "--questions",
                        "--endpoint", "http://127.0.0.1:1/v1"])
        assert code == 0
        assert (tmp_path / "out.svg").exists()
