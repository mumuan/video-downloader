import pytest
import tempfile
import os
from src.config import Config

def test_default_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config(tmpdir)
        assert "bilibili" in cfg.output_dir
        assert os.path.isdir(cfg.output_dir)

def test_set_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config(tmpdir)
        new_dir = os.path.join(tmpdir, "new_output")
        cfg.output_dir = new_dir
        assert cfg.output_dir == new_dir
        assert os.path.isdir(new_dir)

def test_config_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg1 = Config(tmpdir)
        new_dir = os.path.join(tmpdir, "persist")
        cfg1.output_dir = new_dir
        cfg1.save()
        cfg2 = Config(tmpdir)
        assert cfg2.output_dir == new_dir