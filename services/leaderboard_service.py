"""Leaderboard, State Topper, and Gender Topper calculation engine.

Implements rigorous, consistent tie-breaking:
  1. Higher total score
  2. Shorter completion time (time_taken_seconds)
  3. Shared rank / attempt ID for determinism
"""

import db

def get_overall_leaderboard(exam_id=None, limit=100):
    """Retrieve overall leaderboard rankings."""
    params = []
    where_clauses = ["ea.status IN ('evaluated', 'submitted')", "u.is_active = 1"]
    
    if exam_id:
        where_clauses.append("ea.examination_id = %s")
        params.append(exam_id)
        
    sql = f"""
        SELECT ea.id AS attempt_id, ea.overall_rank, ea.total_score, ea.percentage,
               ea.time_taken_seconds, ea.submitted_at,
               u.id AS user_id, u.full_name, u.state, u.gender, u.registration_number,
               e.id AS exam_id, e.title AS exam_title, e.total_marks
        FROM examination_attempts ea
        JOIN users u ON ea.student_id = u.id
        JOIN examinations e ON ea.examination_id = e.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY ea.total_score DESC, ea.time_taken_seconds ASC, ea.id ASC
        LIMIT %s
    """
    params.append(limit)
    rows = db.query_all(sql, tuple(params))
    
    # Assign display rank with tie-handling
    ranked = []
    current_rank = 1
    for idx, r in enumerate(rows):
        if idx > 0:
            prev = rows[idx - 1]
            if r["total_score"] == prev["total_score"] and r["time_taken_seconds"] == prev["time_taken_seconds"]:
                r["rank"] = ranked[-1]["rank"]
            else:
                r["rank"] = idx + 1
        else:
            r["rank"] = 1
        ranked.append(r)
    return ranked

def get_state_toppers(exam_id=None, selected_state=None):
    """Calculate State Topper rankings.
    
    Returns:
      - state_summary: Dict mapping state -> top student info
      - state_leaderboard: List of students ranked within the selected_state
    """
    params = []
    where_clauses = [
        "ea.status IN ('evaluated', 'submitted')",
        "u.is_active = 1",
        "u.state IS NOT NULL",
        "u.state != ''"
    ]
    if exam_id:
        where_clauses.append("ea.examination_id = %s")
        params.append(exam_id)
        
    sql = f"""
        SELECT ea.id AS attempt_id, ea.total_score, ea.percentage,
               ea.time_taken_seconds, ea.submitted_at,
               u.id AS user_id, u.full_name, u.state, u.gender, u.registration_number,
               e.id AS exam_id, e.title AS exam_title, e.total_marks
        FROM examination_attempts ea
        JOIN users u ON ea.student_id = u.id
        JOIN examinations e ON ea.examination_id = e.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY u.state ASC, ea.total_score DESC, ea.time_taken_seconds ASC, ea.id ASC
    """
    rows = db.query_all(sql, tuple(params) if params else None)
    
    # Group by state to identify #1 topper per state
    state_toppers_map = {}
    state_groups = {}
    
    for r in rows:
        st = r["state"]
        if st not in state_groups:
            state_groups[st] = []
        state_groups[st].append(r)
        
        # First one encountered in state is top rank due to ORDER BY
        if st not in state_toppers_map:
            state_toppers_map[st] = r

    # Process specific state leaderboard if selected
    selected_leaderboard = []
    if selected_state and selected_state in state_groups:
        st_rows = state_groups[selected_state]
        for idx, r in enumerate(st_rows):
            if idx > 0:
                prev = st_rows[idx - 1]
                if r["total_score"] == prev["total_score"] and r["time_taken_seconds"] == prev["time_taken_seconds"]:
                    r["state_rank"] = selected_leaderboard[-1]["state_rank"]
                else:
                    r["state_rank"] = idx + 1
            else:
                r["state_rank"] = 1
            selected_leaderboard.append(r)

    # List of all available states with participants
    available_states = sorted(list(state_groups.keys()))

    return {
        "state_toppers": state_toppers_map,
        "selected_leaderboard": selected_leaderboard,
        "available_states": available_states,
        "total_states": len(available_states)
    }

def get_gender_toppers(exam_id=None, selected_gender=None):
    """Calculate Gender Topper rankings.
    
    Excludes undisclosed or missing gender data from gender-specific leaderboards.
    Supports 'Male', 'Female', 'Other' with respectful neutral labels.
    """
    params = []
    where_clauses = [
        "ea.status IN ('evaluated', 'submitted')",
        "u.is_active = 1",
        "u.gender IS NOT NULL",
        "u.gender != ''",
        "LOWER(u.gender) NOT IN ('prefer not to say', 'undisclosed', 'unknown', 'none')"
    ]
    if exam_id:
        where_clauses.append("ea.examination_id = %s")
        params.append(exam_id)

    sql = f"""
        SELECT ea.id AS attempt_id, ea.total_score, ea.percentage,
               ea.time_taken_seconds, ea.submitted_at,
               u.id AS user_id, u.full_name, u.state, u.gender, u.registration_number,
               e.id AS exam_id, e.title AS exam_title, e.total_marks
        FROM examination_attempts ea
        JOIN users u ON ea.student_id = u.id
        JOIN examinations e ON ea.examination_id = e.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY u.gender ASC, ea.total_score DESC, ea.time_taken_seconds ASC, ea.id ASC
    """
    rows = db.query_all(sql, tuple(params) if params else None)

    gender_toppers_map = {}
    gender_groups = {}

    for r in rows:
        gen = r["gender"]
        if gen not in gender_groups:
            gender_groups[gen] = []
        gender_groups[gen].append(r)
        
        if gen not in gender_toppers_map:
            gender_toppers_map[gen] = r

    selected_leaderboard = []
    if selected_gender and selected_gender in gender_groups:
        gen_rows = gender_groups[selected_gender]
        for idx, r in enumerate(gen_rows):
            if idx > 0:
                prev = gen_rows[idx - 1]
                if r["total_score"] == prev["total_score"] and r["time_taken_seconds"] == prev["time_taken_seconds"]:
                    r["gender_rank"] = selected_leaderboard[-1]["gender_rank"]
                else:
                    r["gender_rank"] = idx + 1
            else:
                r["gender_rank"] = 1
            selected_leaderboard.append(r)

    available_genders = sorted(list(gender_groups.keys()))

    return {
        "gender_toppers": gender_toppers_map,
        "selected_leaderboard": selected_leaderboard,
        "available_genders": available_genders
    }

def update_examination_ranks(exam_id):
    """Recalculate overall, state, and gender ranks for all evaluated attempts of an exam."""
    attempts = db.query_all(
        """SELECT ea.id, ea.total_score, ea.time_taken_seconds, u.state, u.gender
           FROM examination_attempts ea
           JOIN users u ON ea.student_id = u.id
           WHERE ea.examination_id = %s AND ea.status IN ('evaluated', 'submitted')
           ORDER BY ea.total_score DESC, ea.time_taken_seconds ASC, ea.id ASC""",
        (exam_id,)
    )
    if not attempts:
        return

    # 1. Overall Ranks
    overall_ranks = {}
    for idx, att in enumerate(attempts):
        if idx > 0:
            prev = attempts[idx - 1]
            if att["total_score"] == prev["total_score"] and att["time_taken_seconds"] == prev["time_taken_seconds"]:
                overall_ranks[att["id"]] = overall_ranks[prev["id"]]
            else:
                overall_ranks[att["id"]] = idx + 1
        else:
            overall_ranks[att["id"]] = 1

    # 2. State Ranks
    state_ranks = {}
    by_state = {}
    for att in attempts:
        st = att.get("state")
        if st:
            by_state.setdefault(st, []).append(att)
            
    for st, st_attempts in by_state.items():
        for idx, att in enumerate(st_attempts):
            if idx > 0:
                prev = st_attempts[idx - 1]
                if att["total_score"] == prev["total_score"] and att["time_taken_seconds"] == prev["time_taken_seconds"]:
                    state_ranks[att["id"]] = state_ranks[prev["id"]]
                else:
                    state_ranks[att["id"]] = idx + 1
            else:
                state_ranks[att["id"]] = 1

    # 3. Gender Ranks
    gender_ranks = {}
    by_gender = {}
    for att in attempts:
        gen = att.get("gender")
        if gen and gen.lower() not in ('prefer not to say', 'undisclosed', 'unknown'):
            by_gender.setdefault(gen, []).append(att)

    for gen, gen_attempts in by_gender.items():
        for idx, att in enumerate(gen_attempts):
            if idx > 0:
                prev = gen_attempts[idx - 1]
                if att["total_score"] == prev["total_score"] and att["time_taken_seconds"] == prev["time_taken_seconds"]:
                    gender_ranks[att["id"]] = gender_ranks[prev["id"]]
                else:
                    gender_ranks[att["id"]] = idx + 1
            else:
                gender_ranks[att["id"]] = 1

    # Update in database
    with db.transaction() as conn:
        cur = conn.cursor()
        for att in attempts:
            a_id = att["id"]
            o_rank = overall_ranks.get(a_id)
            s_rank = state_ranks.get(a_id)
            g_rank = gender_ranks.get(a_id)
            cur.execute(
                """UPDATE examination_attempts
                   SET overall_rank = %s, state_rank = %s, gender_rank = %s
                   WHERE id = %s""",
                (o_rank, s_rank, g_rank, a_id)
            )
        cur.close()
