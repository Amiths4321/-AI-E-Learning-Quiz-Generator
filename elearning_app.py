# elearning_app.py
# streamlit run elearning_app.py

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import streamlit as st
from pathlib     import Path
from course_ai   import (
    generate_course, generate_quiz, grade_mcq,
    grade_open_answer, generate_followup, answer_study_question
)
from course_store import (
    init_db, save_course, save_quiz, save_attempt,
    get_courses, get_course, get_quiz, get_course_quizzes, get_attempts
)

init_db()

st.set_page_config(
    page_title="AI E-Learning",
    page_icon="📚",
    layout="wide"
)

# ── Session state ─────────────────────────────────────────────────────────────
if "current_course_id" not in st.session_state: st.session_state.current_course_id = None
if "current_quiz_id"   not in st.session_state: st.session_state.current_quiz_id   = None
if "quiz_answers"      not in st.session_state: st.session_state.quiz_answers       = {}
if "open_answers"      not in st.session_state: st.session_state.open_answers       = {}
if "quiz_submitted"    not in st.session_state: st.session_state.quiz_submitted     = False
if "chat_history"      not in st.session_state: st.session_state.chat_history       = []
if "learner_name"      not in st.session_state: st.session_state.learner_name       = "Learner"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📚 AI E-Learning")
    st.caption("Generate · Learn · Quiz · Adapt")

    st.divider()

    st.session_state.learner_name = st.text_input(
        "Your name:", value=st.session_state.learner_name
    )

    st.divider()
    st.markdown("**My courses**")
    courses = get_courses()
    if courses:
        for c in courses:
            if st.button(
                f"📖 {c['title'][:35]}",
                key=f"sc_{c['id']}",
                use_container_width=True
            ):
                st.session_state.current_course_id = c["id"]
                st.session_state.quiz_submitted    = False
                st.session_state.quiz_answers      = {}
                st.session_state.open_answers      = {}
                st.session_state.chat_history      = []
                st.rerun()
    else:
        st.caption("No courses yet — create one!")

    st.divider()
    if st.button("+ Create new course", use_container_width=True, type="primary"):
        st.session_state.current_course_id = None
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("📚 AI E-Learning & Quiz Generator")

# ── Course creation ───────────────────────────────────────────────────────────
if st.session_state.current_course_id is None:
    st.subheader("Create a new course")

    creation_method = st.radio(
        "How do you want to create the course?",
        ["From a topic / title", "From a document (PDF/TXT)", "From pasted text"],
        horizontal=True
    )

    content   = ""
    title_val = ""

    if creation_method == "From a topic / title":
        title_val = st.text_input(
            "Course topic:",
            placeholder="e.g. Introduction to Machine Learning, Python for Beginners, RAG Systems"
        )
        content = title_val

    elif creation_method == "From a document (PDF/TXT)":
        uploaded = st.file_uploader("Upload PDF or TXT:", type=["pdf", "txt"])
        if uploaded:
            if uploaded.name.endswith(".pdf"):
                import fitz
                doc     = fitz.open(stream=uploaded.read(), filetype="pdf")
                content = "\n\n".join(page.get_text() for page in doc)
                doc.close()
            else:
                content = uploaded.read().decode("utf-8", errors="replace")
            title_val = uploaded.name.replace(".pdf", "").replace(".txt", "")
            st.success(f"Loaded: {len(content.split())} words")

    elif creation_method == "From pasted text":
        content   = st.text_area("Paste your content:", height=200)
        title_val = st.text_input("Course title (optional):", placeholder="Auto-generated if empty")

    col1, col2, col3 = st.columns(3)
    with col1:
        level       = st.selectbox("Level:", ["Beginner", "Intermediate", "Advanced"])
    with col2:
        num_modules = st.slider("Number of modules:", 2, 8, 4)
    with col3:
        num_mcq     = st.slider("MCQ per module:", 3, 10, 5)
        st.session_state.num_mcq = num_mcq

    if st.button("Generate course", type="primary", disabled=not content):
        with st.spinner("Generating course structure... (30-60 seconds)"):
            course = generate_course(content, title_val, level, num_modules)

        with st.spinner("Saving course..."):
            course_id = save_course(course, source=creation_method)

        st.session_state.current_course_id = course_id
        st.success(f"Course created: {course['title']}")
        st.rerun()

    # Sample courses
    st.divider()
    st.markdown("**Quick start — generate a sample course**")
    sample_topics = [
        "Introduction to Retrieval Augmented Generation (RAG)",
        "Python Data Analysis with Pandas",
        "Machine Learning Fundamentals",
        "Docker and Containerisation for Beginners",
        "Prompt Engineering Best Practices",
    ]
    for i, topic in enumerate(sample_topics):
        if st.button(topic, key=f"sample_{i}", use_container_width=True):
            with st.spinner(f"Generating course on: {topic}..."):
                course    = generate_course(topic, topic, "Intermediate", 4)
                course_id = save_course(course, source="Sample topic")
            st.session_state.current_course_id = course_id
            st.rerun()

    st.stop()

# ── Course viewer ─────────────────────────────────────────────────────────────
course_data = get_course(st.session_state.current_course_id)
if not course_data:
    st.error("Course not found.")
    st.session_state.current_course_id = None
    st.rerun()

course  = course_data["content"]
quizzes = get_course_quizzes(st.session_state.current_course_id)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📖 Course",
    "🧠 Take Quiz",
    "📊 Results",
    "🔄 Adaptive",
    "💬 Study Chat"
])

# ── Tab 1: Course content ─────────────────────────────────────────────────────
with tab1:
    st.title(course.get("title", "Course"))
    col1, col2, col3 = st.columns(3)
    col1.metric("Level",    course.get("level", ""))
    col2.metric("Modules",  len(course.get("modules", [])))
    col3.metric("Duration", course.get("estimated_duration", ""))

    st.markdown(f"**{course.get('description', '')}**")

    objectives = course.get("learning_objectives", [])
    if objectives:
        st.markdown("**Learning objectives:**")
        for obj in objectives:
            st.markdown(f"- {obj}")

    st.divider()

    for module in course.get("modules", []):
        mod_num   = module.get("module_number", 0)
        mod_title = module.get("title", "")

        with st.expander(f"Module {mod_num}: {mod_title}", expanded=(mod_num == 1)):
            st.markdown(f"*{module.get('description', '')}*")
            st.divider()

            for lesson in module.get("lessons", []):
                st.markdown(f"#### Lesson {lesson.get('lesson_number', '')}: {lesson.get('title', '')}")
                st.markdown(lesson.get("content", ""))

                key_points = lesson.get("key_points", [])
                if key_points:
                    st.markdown("**Key points:**")
                    for kp in key_points:
                        st.markdown(f"- {kp}")

                summary = lesson.get("summary", "")
                if summary:
                    st.caption(f"Summary: {summary}")

                st.divider()

            # Generate quiz for this module
            existing_quiz = next(
                (q for q in quizzes if q["module_num"] == mod_num), None
            )
            if existing_quiz:
                st.success(f"Quiz available for this module — go to Take Quiz tab")
            else:
                if st.button(
                    f"Generate quiz for Module {mod_num}",
                    key=f"gen_quiz_{mod_num}"
                ):
                    module_text = module.get("description", "") + " ".join(
                        l.get("content", "") for l in module.get("lessons", [])
                    )
                    with st.spinner("Generating quiz..."):
                        quiz = generate_quiz(module_text, mod_title, st.session_state.get("num_mcq", 5), 2)
                        save_quiz(
                            st.session_state.current_course_id,
                            mod_num, mod_title, quiz
                        )
                    st.success("Quiz generated! Go to Take Quiz tab.")
                    st.rerun()

    # Download course
    st.divider()
    course_md = f"# {course.get('title', '')}\n\n"
    course_md += f"{course.get('description', '')}\n\n"
    for module in course.get("modules", []):
        course_md += f"## Module {module.get('module_number', '')}: {module.get('title', '')}\n\n"
        for lesson in module.get("lessons", []):
            course_md += f"### {lesson.get('title', '')}\n\n{lesson.get('content', '')}\n\n"

    st.download_button(
        "Download course as Markdown",
        course_md,
        file_name = f"{course.get('title', 'course').replace(' ', '_')}.md",
        mime      = "text/markdown"
    )

# ── Tab 2: Take quiz ──────────────────────────────────────────────────────────
with tab2:
    st.subheader("Take a quiz")

    quizzes = get_course_quizzes(st.session_state.current_course_id)

    if not quizzes:
        st.info("No quizzes yet. Go to Course tab and click 'Generate quiz' for any module.")
    else:
        quiz_options = {f"Module {q['module_num']}: {q['module_title']}": q["id"]
                        for q in quizzes}
        selected_quiz_name = st.selectbox("Choose quiz:", list(quiz_options.keys()))
        selected_quiz_id   = quiz_options[selected_quiz_name]

        if selected_quiz_id != st.session_state.current_quiz_id:
            st.session_state.current_quiz_id  = selected_quiz_id
            st.session_state.quiz_answers     = {}
            st.session_state.open_answers     = {}
            st.session_state.quiz_submitted   = False

        quiz_data = get_quiz(selected_quiz_id)
        quiz      = quiz_data.get("quiz", {})
        mcqs      = quiz.get("mcq_questions", [])
        opens     = quiz.get("open_questions", [])

        if not st.session_state.quiz_submitted:
            st.markdown(f"**{len(mcqs)} multiple choice + {len(opens)} open-ended questions**")
            st.divider()

            # MCQ section
            if mcqs:
                st.markdown("### Multiple Choice Questions")
                for q in mcqs:
                    st.markdown(f"**Q{q['id']}. {q['question']}**")
                    st.caption(f"Difficulty: {q.get('difficulty', 'Medium')}")

                    options = q.get("options", {})
                    choices = [f"{k}: {v}" for k, v in options.items()]

                    answer = st.radio(
                        "Select answer:",
                        choices,
                        key=f"mcq_{q['id']}",
                        index=None
                    )
                    if answer:
                        st.session_state.quiz_answers[q["id"]] = answer[0]
                    st.divider()

            # Open-ended section
            if opens:
                st.markdown("### Open-Ended Questions")
                for q in opens:
                    st.markdown(f"**Q{q['id']}. {q['question']}**")
                    st.caption(f"Marks: {q.get('marks', 5)}")
                    answer = st.text_area(
                        "Your answer:",
                        key   = f"open_{q['id']}",
                        height = 100
                    )
                    if answer:
                        st.session_state.open_answers[q["id"]] = answer
                    st.divider()

            answered_mcq  = len(st.session_state.quiz_answers)
            answered_open = len(st.session_state.open_answers)
            total_q       = len(mcqs) + len(opens)
            answered_total = answered_mcq + answered_open

            st.progress(answered_total / total_q if total_q > 0 else 0,
                        text=f"Answered: {answered_total}/{total_q}")

            if st.button("Submit quiz", type="primary",
                         disabled=answered_mcq < len(mcqs)):
                # Grade MCQs
                mcq_result = grade_mcq(mcqs, st.session_state.quiz_answers)

                # Grade open questions with AI
                open_results = []
                for q in opens:
                    user_ans = st.session_state.open_answers.get(q["id"], "")
                    if user_ans:
                        with st.spinner(f"Grading open question {q['id']}..."):
                            result = grade_open_answer(
                                q["question"],
                                q.get("model_answer", ""),
                                user_ans,
                                q.get("marks", 5)
                            )
                        open_results.append({
                            "id":       q["id"],
                            "question": q["question"],
                            "answer":   user_ans,
                            "result":   result
                        })

                # Save attempt
                save_attempt(
                    selected_quiz_id,
                    st.session_state.learner_name,
                    mcq_result["score"],
                    mcq_result["total"],
                    mcq_result["percentage"],
                    {
                        "mcq":  st.session_state.quiz_answers,
                        "open": st.session_state.open_answers
                    }
                )

                st.session_state.quiz_result       = mcq_result
                st.session_state.open_results      = open_results
                st.session_state.quiz_submitted    = True
                st.rerun()

        else:
            # Show results
            result = st.session_state.get("quiz_result", {})
            score  = result.get("percentage", 0)

            col1, col2, col3 = st.columns(3)
            col1.metric("Score",         f"{result.get('score', 0)}/{result.get('total', 0)}")
            col2.metric("Percentage",    f"{score}%")
            col3.metric("Grade",         result.get("grade", ""))

            st.progress(score / 100)

            # Detailed results
            st.divider()
            for r in result.get("results", []):
                icon = "✅" if r["is_correct"] else "❌"
                with st.expander(f"{icon} Q{r['id']}: {r['question'][:60]}"):
                    options = r.get("options", {})
                    for k, v in options.items():
                        mark = ""
                        if k == r["correct_answer"]: mark = " ✅"
                        if k == r["user_answer"] and not r["is_correct"]: mark = " ❌"
                        st.markdown(f"**{k}:** {v}{mark}")
                    if not r["is_correct"]:
                        st.info(f"Explanation: {r['explanation']}")

            # Open question results
            for oq in st.session_state.get("open_results", []):
                with st.expander(f"Open Q{oq['id']}: {oq['question'][:60]}"):
                    st.markdown(f"**Your answer:** {oq['answer']}")
                    res = oq.get("result", {})
                    st.metric("Marks", f"{res.get('marks_awarded', 0)}/{5}")
                    st.markdown(f"**Feedback:** {res.get('feedback', '')}")
                    if res.get("improvements"):
                        st.markdown("**Improvements:**")
                        for imp in res["improvements"]:
                            st.markdown(f"- {imp}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Retake quiz"):
                    st.session_state.quiz_submitted  = False
                    st.session_state.quiz_answers    = {}
                    st.session_state.open_answers    = {}
                    st.rerun()
            with col2:
                if st.button("Get adaptive content →", type="primary"):
                    st.session_state.goto_adaptive = True
                    st.rerun()

# ── Tab 3: Results history ────────────────────────────────────────────────────
with tab3:
    st.subheader("Quiz results history")

    all_quizzes = get_course_quizzes(st.session_state.current_course_id)
    for quiz in all_quizzes:
        attempts = get_attempts(quiz["id"])
        if attempts:
            st.markdown(f"**Module {quiz['module_num']}: {quiz['module_title']}**")
            for att in attempts:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Learner",    att.get("learner", ""))
                col2.metric("Score",      f"{att['score']}/{att['total']}")
                col3.metric("Percentage", f"{att['percentage']}%")
                col4.caption(att.get("created_at", "")[:16])
            st.divider()

# ── Tab 4: Adaptive learning ──────────────────────────────────────────────────
with tab4:
    st.subheader("Adaptive follow-up content")

    if not st.session_state.get("quiz_submitted"):
        st.info("Complete a quiz first to get adaptive content.")
    else:
        result    = st.session_state.get("quiz_result", {})
        score_pct = result.get("percentage", 0)

        wrong_topics = [
            r["question"][:50]
            for r in result.get("results", [])
            if not r["is_correct"]
        ]

        if score_pct >= 80:
            st.success(f"Great score ({score_pct}%)! Here's advanced extension content:")
        else:
            st.warning(f"Score: {score_pct}%. Here's targeted remedial content:")

        current_quiz = get_quiz(st.session_state.current_quiz_id or 0)
        if current_quiz:
            quiz_data     = current_quiz.get("quiz", {})
            module_content = quiz_data.get("module_title", "")

            with st.spinner("Generating adaptive content..."):
                followup = generate_followup(module_content, score_pct, wrong_topics)
            st.markdown(followup)

# ── Tab 5: Study chat ─────────────────────────────────────────────────────────
with tab5:
    st.subheader("Study chat")
    st.caption("Ask anything about the course material")

    # Build course text for RAG
    course_text = f"{course.get('title', '')}\n{course.get('description', '')}\n"
    for module in course.get("modules", []):
        course_text += f"\n{module.get('title', '')}: {module.get('description', '')}\n"
        for lesson in module.get("lessons", []):
            course_text += f"\n{lesson.get('content', '')}\n"

    # Chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Quick questions
    quick_questions = [
        "Summarise this course in 3 bullet points",
        "What are the most important concepts?",
        "Give me a real-world example of the main topic",
        "What should I study first if I'm a beginner?",
    ]
    cols = st.columns(2)
    for i, q in enumerate(quick_questions):
        if cols[i % 2].button(q, key=f"sq_{i}", use_container_width=True):
            st.session_state["study_q"] = q

    question = st.chat_input("Ask about the course...") or st.session_state.pop("study_q", None)

    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Tutor thinking..."):
                answer = answer_study_question(
                    question, course_text,
                    st.session_state.chat_history[:-1]
                )
            st.markdown(answer)

        st.session_state.chat_history.append({"role": "assistant", "content": answer})