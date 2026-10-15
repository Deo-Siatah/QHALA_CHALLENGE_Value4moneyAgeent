import pytest
from langgraph.checkpoint.memory import InMemorySaver

from agent import run
from agent.run import bid_paths, main, new_run_id, parse_args, preflight


@pytest.fixture
def faked(monkeypatch, tmp_path):
    """Fake the checkpointer with memory, all six data nodes, and filing, so no real write happens."""
    monkeypatch.setattr(run, "checkpointer", lambda: _InMemory())
    monkeypatch.setattr(run, "init_tracing", lambda *args: False)
    monkeypatch.setattr(run, "flush", lambda: None)
    monkeypatch.setattr(run.settings, "outputs_dir", tmp_path)
    monkeypatch.setattr(run.settings, "llm_model", "fake-model")
    monkeypatch.setattr(run.settings, "database_url", "postgresql://fake")

    import agent.graph as graph_module
    from agent.nodes.approval import approval_node

    monkeypatch.setattr(graph_module, "intake_node",
                        lambda s: {"bids": [{"bidder": "Apex", "stated_total": 3150000.0}]})
    monkeypatch.setattr(graph_module, "research_node",
                        lambda s: {"search_attempts": 1, "search": {"match": "loose"}})
    monkeypatch.setattr(graph_module, "quality_check_node", lambda s: {"pool_size": 12})
    monkeypatch.setattr(graph_module, "score_node",
                        lambda s: {"benchmark": {"n": 12, "confidence": "medium", "median_kes": 3300000.0,
                                                 "q1_kes": 2000000.0, "q3_kes": 4900000.0,
                                                 "bids": [{"bidder": "Apex", "total": 3150000.0,
                                                           "pct_vs_median": -4.5,
                                                           "position": "within_range"}]}})
    monkeypatch.setattr(graph_module, "draft_node",
                        lambda s: {"review_markdown": "# Price review evidence: T/1\n\ndraft body\n",
                                   "verify_rounds": s.get("verify_rounds", 0) + 1,
                                   "summary": "Twelve awards were compared."})
    monkeypatch.setattr(graph_module, "verify_sources_node", lambda s: {"verify_ok": True})
    monkeypatch.setattr(graph_module, "approval_node", approval_node)
    monkeypatch.setattr(graph_module, "file_node",
                        lambda s: {"submission": {"report_id": 3, "run_id": s["run_id"],
                                                  "approved_by": s["approved_by"],
                                                  "file_path": "outputs/reports/x.md",
                                                  "submitted_at": "2026-10-14 22:00:00Z"}})
    return tmp_path


class _InMemory:
    """A context manager yielding one InMemorySaver shared by both calls of a run."""

    saver = InMemorySaver()

    def __enter__(self):
        return self.saver

    def __exit__(self, *args):
        return False


def test_a_run_id_sorts_by_time_and_is_a_safe_file_name():
    run_id = new_run_id()

    assert run_id.startswith("run-")
    assert len(run_id) == len("run-20261014-224512")
    assert all(character.isalnum() or character in "-_" for character in run_id)


def test_named_pdfs_are_taken_from_the_bids_directory(tmp_path):
    (tmp_path / "one.pdf").write_bytes(b"")
    (tmp_path / "two.pdf").write_bytes(b"")

    chosen = bid_paths(tmp_path, ["two.pdf"])

    assert chosen == [str(tmp_path / "two.pdf")]


def test_every_pdf_is_used_when_none_are_named(tmp_path):
    (tmp_path / "one.pdf").write_bytes(b"")
    (tmp_path / "two.pdf").write_bytes(b"")

    assert bid_paths(tmp_path, None) == [str(tmp_path / "one.pdf"), str(tmp_path / "two.pdf")]


def test_an_empty_bids_directory_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError) as err:
        bid_paths(tmp_path, None)

    assert "make_sample_bids" in str(err.value)


def test_starting_without_a_model_is_refused_before_anything_runs(monkeypatch):
    monkeypatch.setattr(run.settings, "llm_model", "")

    with pytest.raises(SystemExit) as err:
        preflight()

    assert "LLM_MODEL" in str(err.value)


def test_a_decision_without_a_run_to_resume_is_refused():
    with pytest.raises(SystemExit):
        parse_args(["--decision", "approved", "--approved-by", "Grace Wanjiku"])


def test_resuming_without_a_decision_is_refused():
    with pytest.raises(SystemExit):
        parse_args(["--resume", "run-1"])


def test_a_run_pauses_for_approval_and_writes_the_draft(faked, capsys):
    code = main(["--pdfs", "one.pdf", "--run-id", "run-test", "--bids-dir", str(faked)])

    out = capsys.readouterr().out
    assert code == run.PAUSED
    assert "waiting for a decision" in out
    assert "--resume run-test --decision approved" in out
    draft = faked / "drafts" / "run-test.md"
    assert draft.exists()
    assert draft.read_text(encoding="utf-8").startswith("# Price review evidence")
    assert not (faked / "reports").exists()


def test_the_run_can_then_be_approved_and_filed(faked, capsys):
    assert main(["--pdfs", "one.pdf", "--run-id", "run-test2", "--bids-dir", str(faked)]) == run.PAUSED

    code = main(["--resume", "run-test2", "--decision", "approved",
                 "--approved-by", "Grace Wanjiku", "--note", "figures checked"])

    out = capsys.readouterr().out
    assert code == run.FILED
    assert "run-test2 filed" in out
    assert "Grace Wanjiku" in out


def test_a_rejected_run_files_nothing(faked, capsys):
    main(["--pdfs", "one.pdf", "--run-id", "run-test3", "--bids-dir", str(faked)])

    code = main(["--resume", "run-test3", "--decision", "rejected",
                 "--approved-by", "Grace Wanjiku", "--note", "scope unclear"])

    assert code == run.DECLINED
    assert "filed nothing" in capsys.readouterr().out


def test_resuming_a_run_that_does_not_exist_says_so(faked, capsys):
    code = main(["--resume", "run-never-started", "--decision", "approved",
                 "--approved-by", "Grace Wanjiku"])

    err = capsys.readouterr().err
    assert code == run.NOT_FILED
    assert "no run 'run-never-started'" in err
    assert "never started" in err


def test_a_malformed_decision_is_refused_by_the_approval_node(faked):
    main(["--pdfs", "one.pdf", "--run-id", "run-test4", "--bids-dir", str(faked)])

    with pytest.raises(ValueError) as err:
        main(["--resume", "run-test4", "--decision", "approved", "--approved-by", "agent"])

    assert "placeholder" in str(err.value)