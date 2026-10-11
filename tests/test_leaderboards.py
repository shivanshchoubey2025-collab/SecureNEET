"""Tests for Overall Leaderboard, State Topper, Gender Topper, and Tie-breaking."""

import pytest
import db
from services.leaderboard_service import (
    get_overall_leaderboard, get_state_toppers, get_gender_toppers, update_examination_ranks
)

@pytest.fixture
def scored_exam_attempts(seed_users):
    """Seed exam with attempts having known scores, states, genders, and times."""
    admin_id = seed_users["admin"]["id"]
    exam_id = db.execute(
        """INSERT INTO examinations
           (title, code, duration_minutes, total_marks, is_published, created_by)
           VALUES ('Rank Test Exam', 'RANK-01', 180, 100, 1, %s)""",
        (admin_id,)
    )

    s1 = seed_users["student1"]["id"] # Maharashtra, Male
    s2 = seed_users["student2"]["id"] # Maharashtra, Female
    s3 = seed_users["student3"]["id"] # Delhi, Prefer not to say

    # S1: Score 80, time 5000s
    att1 = db.execute(
        """INSERT INTO examination_attempts
           (examination_id, student_id, start_time, deadline_time, submitted_at, status, total_score, percentage, time_taken_seconds)
           VALUES (%s, %s, NOW(), NOW(), NOW(), 'evaluated', 80.0, 80.0, 5000)""",
        (exam_id, s1)
    )

    # S2: Score 80, time 4000s (Tied on score with S1, but finished FASTER -> should break tie and rank higher!)
    att2 = db.execute(
        """INSERT INTO examination_attempts
           (examination_id, student_id, start_time, deadline_time, submitted_at, status, total_score, percentage, time_taken_seconds)
           VALUES (%s, %s, NOW(), NOW(), NOW(), 'evaluated', 80.0, 80.0, 4000)""",
        (exam_id, s2)
    )

    # S3: Score 90, time 6000s (Highest score -> AIR 1)
    att3 = db.execute(
        """INSERT INTO examination_attempts
           (examination_id, student_id, start_time, deadline_time, submitted_at, status, total_score, percentage, time_taken_seconds)
           VALUES (%s, %s, NOW(), NOW(), NOW(), 'evaluated', 90.0, 90.0, 6000)""",
        (exam_id, s3)
    )

    update_examination_ranks(exam_id)
    return {"exam_id": exam_id, "att1": att1, "att2": att2, "att3": att3}

def test_overall_leaderboard_and_tie_breaking(scored_exam_attempts):
    """Test that higher scores rank top, and ties are broken by shorter completion time."""
    exam_id = scored_exam_attempts["exam_id"]
    leaderboard = get_overall_leaderboard(exam_id=exam_id)

    assert len(leaderboard) == 3
    # S3 (score 90) must be Rank 1
    assert leaderboard[0]["full_name"] == "Student Gamma"
    assert leaderboard[0]["rank"] == 1
    assert float(leaderboard[0]["total_score"]) == 90.0

    # S2 and S1 both scored 80. S2 took 4000s, S1 took 5000s.
    # Therefore, S2 must be Rank 2, and S1 must be Rank 3!
    assert leaderboard[1]["full_name"] == "Student Beta"
    assert leaderboard[1]["rank"] == 2
    assert leaderboard[1]["time_taken_seconds"] == 4000

    assert leaderboard[2]["full_name"] == "Student Alpha"
    assert leaderboard[2]["rank"] == 3
    assert leaderboard[2]["time_taken_seconds"] == 5000

def test_state_topper_rankings(scored_exam_attempts):
    """Test that State Toppers identify the top student per state."""
    exam_id = scored_exam_attempts["exam_id"]
    data = get_state_toppers(exam_id=exam_id)

    state_toppers = data["state_toppers"]
    # Delhi Topper must be Student Gamma (score 90)
    assert "Delhi" in state_toppers
    assert state_toppers["Delhi"]["full_name"] == "Student Gamma"

    # Maharashtra Topper must be Student Beta (score 80 in 4000s > Student Alpha's 5000s)
    assert "Maharashtra" in state_toppers
    assert state_toppers["Maharashtra"]["full_name"] == "Student Beta"

def test_gender_topper_and_undisclosed_exclusion(scored_exam_attempts):
    """Test that Gender Topper ranks Male and Female, and excludes undisclosed."""
    exam_id = scored_exam_attempts["exam_id"]
    data = get_gender_toppers(exam_id=exam_id)

    gender_toppers = data["gender_toppers"]
    # Female Topper: Student Beta
    assert "Female" in gender_toppers
    assert gender_toppers["Female"]["full_name"] == "Student Beta"

    # Male Topper: Student Alpha
    assert "Male" in gender_toppers
    assert gender_toppers["Male"]["full_name"] == "Student Alpha"

    # S3 selected "Prefer not to say" -> MUST NOT appear in gender_toppers!
    assert "Prefer not to say" not in gender_toppers
    for topper in gender_toppers.values():
        assert topper["full_name"] != "Student Gamma"
