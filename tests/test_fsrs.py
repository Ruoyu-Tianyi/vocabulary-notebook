"""FSRS 算法属性 + 边界测试。"""
import pytest
from fsrs import (
    retrievability,
    initial_stability,
    initial_difficulty,
    next_difficulty,
    next_recall_stability,
    next_forget_stability,
    next_interval,
)


# ── Retrievability ─────────────────────────────────────

def test_retrievability_at_zero_elapsed_is_one():
    """刚学完 (elapsed=0) 回忆概率应为 1.0。"""
    assert retrievability(elapsed_days=0, stability=10) == pytest.approx(1.0, abs=1e-9)


def test_retrievability_monotonically_decreases_in_time():
    """时间越长，回忆概率越低。"""
    r0 = retrievability(0, 10)
    r5 = retrievability(5, 10)
    r20 = retrievability(20, 10)
    assert r0 > r5 > r20
    assert r20 > 0  # 不应归零


def test_retrievability_monotonically_increases_in_stability():
    """稳定性越高，回忆概率越高（同等 elapsed）。"""
    r_low = retrievability(10, 5)
    r_high = retrievability(10, 50)
    assert r_low < r_high


# ── Initial values for new cards ───────────────────────

def test_initial_stability_good_again_has_ordering():
    """新词 Good 评分的初始稳定性 > Hard > Again。"""
    s_again = initial_stability(1)
    s_hard = initial_stability(2)
    s_good = initial_stability(3)
    s_easy = initial_stability(4)
    assert s_again < s_hard < s_good < s_easy


def test_initial_difficulty_clamped_to_range():
    """初始难度应在 [1, 10] 范围内。"""
    for r in (1, 2, 3, 4):
        d = initial_difficulty(r)
        assert 1.0 <= d <= 10.0


# ── Difficulty updates ─────────────────────────────────

def test_next_difficulty_again_increases_difficulty():
    """Again 评分应增加难度（更难记住）。"""
    d = 5.0
    new_d = next_difficulty(d, rating=1)
    assert new_d > d


def test_next_difficulty_easy_decreases_difficulty():
    """Easy 评分应降低难度（更好记住）。"""
    d = 5.0
    new_d = next_difficulty(d, rating=4)
    assert new_d < d


# ── Stability updates ──────────────────────────────────

def test_again_decreases_stability():
    """Again 后稳定性应下降。"""
    s = 10.0
    d = 5.0
    r = retrievability(5, s)  # 0.66
    new_s = next_forget_stability(d, s, r)
    assert new_s < s


def test_good_increases_stability():
    """Good 后稳定性应上升。"""
    s = 10.0
    d = 5.0
    r = retrievability(5, s)
    new_s = next_recall_stability(d, s, r, rating=3)
    assert new_s > s


def test_easy_increases_stability_more_than_good():
    """Easy 应比 Good 让稳定性涨得更多。"""
    s, d = 10.0, 5.0
    r = retrievability(5, s)
    s_good = next_recall_stability(d, s, r, rating=3)
    s_easy = next_recall_stability(d, s, r, rating=4)
    assert s_easy > s_good


# ── Interval ───────────────────────────────────────────

def test_next_interval_zero_at_zero_stability():
    """stability=0 时 interval 应为 0（或极小）。"""
    assert next_interval(0) == 0


def test_next_interval_grows_with_stability():
    """稳定性越高，下次复习间隔越长。"""
    i_low = next_interval(5)
    i_high = next_interval(50)
    assert i_low < i_high
