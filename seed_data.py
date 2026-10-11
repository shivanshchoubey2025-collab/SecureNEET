"""Seed data script for SecureNEET.

Creates:
  1. Default Admin & Question Manager accounts
  2. Diverse sample students across Indian states & genders
  3. Official NEET Mock Examination with authentic Physics, Chemistry, Botany, and Zoology questions
  4. Sample attempts and answers for demonstrating Overall, State Topper, and Gender Topper leaderboards
"""

import sys
from datetime import datetime, timedelta
import db
from auth import hash_password

def seed_all():
    print("Initializing database...")
    db.init_db()

    print("Seeding administrative accounts...")
    # 1. Admin
    admin_id = db.query_one("SELECT id FROM users WHERE email = %s", ("admin@secureneet.org",))
    if not admin_id:
        admin_id = db.execute(
            """INSERT INTO users (full_name, email, password_hash, role, state, gender, registration_number, is_active, created_at)
               VALUES (%s, %s, %s, 'admin', 'Delhi', 'Male', 'ADMIN001', 1, NOW())""",
            ("Dr. Rajesh Malhotra (Chief Controller)", "admin@secureneet.org", hash_password("Admin@12345"))
        )
    else:
        admin_id = admin_id["id"]

    # 2. Question Manager
    qm_id = db.query_one("SELECT id FROM users WHERE email = %s", ("qm@secureneet.org",))
    if not qm_id:
        qm_id = db.execute(
            """INSERT INTO users (full_name, email, password_hash, role, state, gender, registration_number, is_active, created_at)
               VALUES (%s, %s, %s, 'question_manager', 'Karnataka', 'Female', 'QM001', 1, NOW())""",
            ("Dr. Sunita Kulkarni (Academics Head)", "qm@secureneet.org", hash_password("Manager@12345"))
        )
    else:
        qm_id = qm_id["id"]

    print("Seeding students across various states and genders...")
    students_data = [
        ("Aarav Sharma", "aarav.sharma@example.com", "Delhi", "Male", "NEET2026001"),
        ("Ananya Iyer", "ananya.iyer@example.com", "Tamil Nadu", "Female", "NEET2026002"),
        ("Rohan Deshmukh", "rohan.deshmukh@example.com", "Maharashtra", "Male", "NEET2026003"),
        ("Sneha Roy", "sneha.roy@example.com", "West Bengal", "Female", "NEET2026004"),
        ("Priya Patel", "priya.patel@example.com", "Gujarat", "Female", "NEET2026005"),
        ("Vikram Singh", "vikram.singh@example.com", "Rajasthan", "Male", "NEET2026006"),
        ("Alex Fernandes", "alex.fernandes@example.com", "Goa", "Other", "NEET2026007"),
        ("Harshita Choudhary", "harshita.c@example.com", "Uttar Pradesh", "Female", "NEET2026008"),
        ("Kavya Nambiar", "kavya.n@example.com", "Kerala", "Female", "NEET2026009"),
        ("Rahul Verma", "rahul.v@example.com", "Bihar", "Prefer not to say", "NEET2026010"),
    ]

    student_ids = {}
    for name, email, state, gender, reg_no in students_data:
        existing = db.query_one("SELECT id FROM users WHERE email = %s", (email,))
        if not existing:
            s_id = db.execute(
                """INSERT INTO users (full_name, email, password_hash, role, state, gender, registration_number, is_active, created_at)
                   VALUES (%s, %s, %s, 'student', %s, %s, %s, 1, NOW())""",
                (name, email, hash_password("Student@12345"), state, gender, reg_no)
            )
            student_ids[email] = s_id
        else:
            student_ids[email] = existing["id"]

    print("Seeding NEET Mock Examinations...")
    exam = db.query_one("SELECT id FROM examinations WHERE code = %s", ("NEET-MOCK-2026-A",))
    if not exam:
        exam_id = db.execute(
            """INSERT INTO examinations
               (title, code, description, duration_minutes, total_marks, passing_marks, positive_marks, negative_marks, is_published, created_by, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, NOW())""",
            ("NEET (UG) 2026 National Full-Length Mock Test 01",
             "NEET-MOCK-2026-A",
             "Comprehensive simulated All-India examination matching the exact NTA NEET (UG) pattern. Includes Physics, Chemistry, Botany, and Zoology with +4 for correct, -1 for incorrect.",
             180, 720, 360, 4.0, 1.0, admin_id)
        )
    else:
        exam_id = exam["id"]

    print("Seeding NEET Questions across 4 subjects...")
    sample_questions = [
        # PHYSICS
        {
            "subject": "Physics",
            "topic": "Mechanics & Kinematics",
            "question_text": "A particle starts from rest with a uniform acceleration. If the distance covered in the first 10 seconds is S1 and in the next 10 seconds is S2, then what is the relationship between S1 and S2?",
            "option_a": "S2 = S1",
            "option_b": "S2 = 2 S1",
            "option_c": "S2 = 3 S1",
            "option_d": "S2 = 4 S1",
            "correct_option": "C",
            "explanation": "Distance covered in first 10s: S1 = 0.5*a*(10)^2 = 50a. Distance in 20s: S = 0.5*a*(20)^2 = 200a. S2 = S - S1 = 150a = 3 S1."
        },
        {
            "subject": "Physics",
            "topic": "Current Electricity",
            "question_text": "A wire of resistance R is stretched uniformly such that its radius decreases to half of its initial value. What is its new resistance?",
            "option_a": "2 R",
            "option_b": "4 R",
            "option_c": "8 R",
            "option_d": "16 R",
            "correct_option": "D",
            "explanation": "Since volume is constant, A1*L1 = A2*L2. If radius r2 = r1/2, area A2 = A1/4, so L2 = 4*L1. Resistance R' = rho * L2 / A2 = rho * (4L1) / (A1/4) = 16 R."
        },
        {
            "subject": "Physics",
            "topic": "Electromagnetic Waves",
            "question_text": "Which of the following electromagnetic waves has the shortest wavelength?",
            "option_a": "Microwaves",
            "option_b": "Infrared rays",
            "option_c": "Ultraviolet rays",
            "option_d": "Gamma rays",
            "correct_option": "D",
            "explanation": "Gamma rays possess the highest frequency and shortest wavelength in the electromagnetic spectrum (< 10^-12 m)."
        },
        # CHEMISTRY
        {
            "subject": "Chemistry",
            "topic": "Chemical Bonding",
            "question_text": "Which of the following molecules has a linear molecular geometry and zero dipole moment?",
            "option_a": "SO2",
            "option_b": "CO2",
            "option_c": "H2O",
            "option_d": "O3",
            "correct_option": "B",
            "explanation": "Carbon dioxide (CO2) has sp hybridization with bond angle 180 degrees. The two equal opposite C=O dipole vectors cancel each other out."
        },
        {
            "subject": "Chemistry",
            "topic": "Organic Chemistry - Haloalkanes",
            "question_text": "In SN2 substitution reactions, the reaction proceeds with which stereochemical outcome?",
            "option_a": "Retention of configuration",
            "option_b": "Complete inversion of configuration (Walden inversion)",
            "option_c": "Racemization",
            "option_d": "Partial retention",
            "correct_option": "B",
            "explanation": "The nucleophile attacks from the backside of the carbon-leaving group bond simultaneously in a concerted mechanism, leading to complete inversion."
        },
        {
            "subject": "Chemistry",
            "topic": "Electrochemistry",
            "question_text": "During the electrolysis of aqueous NaCl using inert electrodes, the product liberated at the anode is:",
            "option_a": "Sodium metal",
            "option_b": "Hydrogen gas (H2)",
            "option_c": "Chlorine gas (Cl2)",
            "option_d": "Oxygen gas (O2)",
            "correct_option": "C",
            "explanation": "Due to the overpotential of oxygen, chloride ions are preferentially oxidized at the anode to form Cl2 gas."
        },
        # BOTANY
        {
            "subject": "Botany",
            "topic": "Plant Physiology - Photosynthesis",
            "question_text": "In C4 plants, the primary carbon dioxide (CO2) acceptor in mesophyll cells is:",
            "option_a": "RuBP (Ribulose 1,5-bisphosphate)",
            "option_b": "PEP (Phosphoenolpyruvate)",
            "option_c": "PGA (3-Phosphoglycerate)",
            "option_d": "OAA (Oxaloacetic acid)",
            "correct_option": "B",
            "explanation": "In mesophyll cells of C4 plants, atmospheric CO2 is accepted by phosphoenolpyruvate (PEP) catalyzed by PEP carboxylase."
        },
        {
            "subject": "Botany",
            "topic": "Genetics & Inheritance",
            "question_text": "What is the typical phenotypic ratio of a Mendelian dihybrid test cross involving two independently assorting heterozygous genes?",
            "option_a": "9 : 3 : 3 : 1",
            "option_b": "1 : 1 : 1 : 1",
            "option_c": "3 : 1",
            "option_d": "9 : 7",
            "correct_option": "B",
            "explanation": "Crossing RrYy with rryy yields four phenotypic classes in equal proportions: 1:1:1:1."
        },
        # ZOOLOGY
        {
            "subject": "Zoology",
            "topic": "Human Physiology - Endocrine System",
            "question_text": "Which hormone is synthesized by the hypothalamus and stored and released by the posterior pituitary gland (neurohypophysis)?",
            "option_a": "Growth Hormone",
            "option_b": "Thyroid Stimulating Hormone (TSH)",
            "option_c": "Oxytocin",
            "option_d": "Prolactin",
            "correct_option": "C",
            "explanation": "Oxytocin and Vasopressin (ADH) are synthesized by neurosecretory neurons in the hypothalamus and transported axonally to the posterior pituitary for release."
        },
        {
            "subject": "Zoology",
            "topic": "Human Physiology - Circulatory System",
            "question_text": "The pacemaker of the human heart that generates action potentials at the highest intrinsic rate is:",
            "option_a": "Atrioventricular (AV) Node",
            "option_b": "Sinoatrial (SA) Node",
            "option_c": "Bundle of His",
            "option_d": "Purkinje Fibres",
            "correct_option": "B",
            "explanation": "The Sinoatrial (SA) node located in the right atrium initiates rhythmic cardiac impulses at approximately 70-75 bpm."
        }
    ]

    for q in sample_questions:
        existing = db.query_one(
            "SELECT id FROM questions WHERE examination_id = %s AND question_text = %s",
            (exam_id, q["question_text"])
        )
        if not existing:
            db.execute(
                """INSERT INTO questions
                   (examination_id, subject, topic, question_text, option_a, option_b, option_c, option_d,
                    correct_option, marks, negative_marks, explanation, created_by, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 4.0, 1.0, %s, %s, NOW())""",
                (exam_id, q["subject"], q["topic"], q["question_text"],
                 q["option_a"], q["option_b"], q["option_c"], q["option_d"],
                 q["correct_option"], q["explanation"], qm_id)
            )

    print("Seeding sample completed attempts for leaderboards...")
    # Seed mock attempts for students with realistic answers
    all_questions = db.query_all("SELECT id, correct_option FROM questions WHERE examination_id = %s", (exam_id,))
    
    # Pre-calculated performance profiles for top students
    # (student_email, correct_indexes, wrong_indexes, time_taken)
    perf_profiles = [
        ("ananya.iyer@example.com", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [], 5400), # 10/10 correct = 40 marks (Tamil Nadu State Topper, Female Topper)
        ("aarav.sharma@example.com", [0, 1, 2, 3, 4, 5, 6, 7, 8], [9], 5800), # 9 correct, 1 wrong = 35 marks (Delhi State Topper, Male Topper)
        ("rohan.deshmukh@example.com", [0, 1, 2, 3, 4, 5, 6, 7], [8, 9], 6100), # 8 correct, 2 wrong = 30 marks (Maharashtra State Topper)
        ("sneha.roy@example.com", [0, 1, 2, 3, 4, 5, 6, 7], [8, 9], 6300), # 8 correct, 2 wrong = 30 marks (West Bengal State Topper, tie broken by time)
        ("priya.patel@example.com", [0, 1, 2, 3, 4, 5], [6, 7, 8, 9], 6500), # 6 correct, 4 wrong = 20 marks (Gujarat State Topper)
        ("vikram.singh@example.com", [0, 1, 2, 3, 4], [5, 6, 7, 8, 9], 6900), # 5 correct, 5 wrong = 15 marks (Rajasthan State Topper)
        ("alex.fernandes@example.com", [0, 1, 2, 3, 4, 5, 6], [7, 8, 9], 6400), # 7 correct, 3 wrong = 25 marks (Goa State Topper, Other Gender Topper)
        ("harshita.choudhary@example.com", [0, 1, 2, 3, 4, 5, 6], [7, 8, 9], 6600), # 25 marks (Uttar Pradesh State Topper)
    ]

    for email, correct_idx_list, wrong_idx_list, time_sec in perf_profiles:
        s_id = student_ids.get(email)
        if not s_id:
            continue
            
        existing_attempt = db.query_one(
            "SELECT id FROM examination_attempts WHERE examination_id = %s AND student_id = %s",
            (exam_id, s_id)
        )
        if existing_attempt:
            continue
            
        start_time = datetime.now() - timedelta(hours=3)
        deadline = start_time + timedelta(minutes=180)
        submitted = start_time + timedelta(seconds=time_sec)
        
        attempt_id = db.execute(
            """INSERT INTO examination_attempts
               (examination_id, student_id, start_time, deadline_time, submitted_at, status, time_taken_seconds)
               VALUES (%s, %s, %s, %s, %s, 'in_progress', %s)""",
            (exam_id, s_id, start_time, deadline, submitted, time_sec)
        )
        
        # Save answers
        for idx, q_row in enumerate(all_questions):
            q_id = q_row["id"]
            corr = q_row["correct_option"]
            if idx in correct_idx_list:
                sel = corr
            elif idx in wrong_idx_list:
                # pick a wrong option
                options = ['A', 'B', 'C', 'D']
                options.remove(corr)
                sel = options[0]
            else:
                sel = None
                
            if sel:
                db.execute(
                    """INSERT INTO student_answers
                       (attempt_id, question_id, selected_option, is_marked_for_review, answered_at)
                       VALUES (%s, %s, %s, 0, NOW())""",
                    (attempt_id, q_id, sel)
                )

        # Evaluate attempt
        from services.exam_service import evaluate_attempt
        evaluate_attempt(attempt_id, status="evaluated")

    # Update examination rankings across overall, state, and gender
    from services.leaderboard_service import update_examination_ranks
    update_examination_ranks(exam_id)

    print("Seeding complete! Database is ready with sample tests and topper leaderboards.")

if __name__ == '__main__':
    seed_all()
