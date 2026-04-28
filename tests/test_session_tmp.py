import os
import shutil
import pytest


def test_get_session_tmp_dir_creates_dir():
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    session_id = "test_user_001"
    path = get_session_tmp_dir(session_id)
    try:
        assert os.path.isdir(path)
        assert path.startswith("tmp" + os.sep)
        assert len(os.path.basename(path)) == 8  # sha256前8位
    finally:
        cleanup_session_tmp(session_id)


def test_get_session_tmp_dir_same_id_same_path():
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    session_id = "test_user_002"
    path1 = get_session_tmp_dir(session_id)
    path2 = get_session_tmp_dir(session_id)
    try:
        assert path1 == path2
    finally:
        cleanup_session_tmp(session_id)


def test_get_session_tmp_dir_different_ids_different_paths():
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    path1 = get_session_tmp_dir("user:group_a")
    path2 = get_session_tmp_dir("user:group_b")
    try:
        assert path1 != path2
    finally:
        cleanup_session_tmp("user:group_a")
        cleanup_session_tmp("user:group_b")


def test_cleanup_session_tmp_removes_dir():
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    session_id = "test_user_003"
    path = get_session_tmp_dir(session_id)
    assert os.path.isdir(path)
    cleanup_session_tmp(session_id)
    assert not os.path.exists(path)


def test_cleanup_session_tmp_nonexistent_is_noop():
    from common.session_tmp import cleanup_session_tmp
    # 不存在的 session，不应抛异常
    cleanup_session_tmp("nonexistent_session_xyz")
