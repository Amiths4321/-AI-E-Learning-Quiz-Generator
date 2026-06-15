# course_ai.py
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST  = os.getenv("OLLAMA_HOST",  "http://10.22.39.192:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:latest")
FENCE        = "```"


def call_llm(prompt: str, max_tokens: int = 2048) -> str:
    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model":   OLLAMA_MODEL,
            "prompt":  prompt,
            "stream":  False,
            "options": {"temperature": 0.3, "num_predict": max_tokens}
        },
        timeout=180
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def parse_json(raw: str) -> any:
    """Safely parse JSON from LLM response."""
    if FENCE in raw:
        parts = raw.split(FENCE)
        for part in parts:
            if part.startswith("json"):
                raw = part[4:].strip()
                break
            elif part.strip().startswith(("{", "[")):
                raw = part.strip()
                break
    try:
        return json.loads(raw.strip())
    except Exception:
        return None


# ── 1. Generate course structure ──────────────────────────────────────────────

def generate_course(
    content:    str,
    title:      str = "",
    level:      str = "Intermediate",
    num_modules: int = 4
) -> dict:
    """
    Generate a full course structure from content or topic.
    Returns { title, description, objectives, modules }
    """
    prompt = (
        f"You are an expert curriculum designer and instructional designer.\n"
        f"Create a structured e-learning course from the content below.\n\n"
        f"COURSE TITLE: {title or 'Auto-generate an appropriate title'}\n"
        f"LEVEL: {level} (Beginner / Intermediate / Advanced)\n"
        f"NUMBER OF MODULES: {num_modules}\n\n"
        f"CONTENT / TOPIC:\n{content[:4000]}\n\n"
        f"Generate a complete course in this EXACT JSON format:\n"
        f"{FENCE}json\n"
        "{\n"
        '  "title": "Course title",\n'
        '  "description": "2-3 sentence course overview",\n'
        '  "level": "Intermediate",\n'
        '  "estimated_duration": "2 hours",\n'
        '  "learning_objectives": [\n'
        '    "By the end of this course, learners will be able to..."\n'
        "  ],\n"
        '  "modules": [\n'
        "    {\n"
        '      "module_number": 1,\n'
        '      "title": "Module title",\n'
        '      "description": "What this module covers",\n'
        '      "lessons": [\n'
        "        {\n"
        '          "lesson_number": 1,\n'
        '          "title": "Lesson title",\n'
        '          "content": "Full lesson explanation in 150-200 words",\n'
        '          "key_points": ["point 1", "point 2", "point 3"],\n'
        '          "summary": "One sentence summary"\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n"
        f"{FENCE}\n\n"
        "Make lessons detailed, educational, and easy to understand."
    )

    raw    = call_llm(prompt, max_tokens=3000)
    result = parse_json(raw)

    if not result:
        return {
            "title":               title or "Generated Course",
            "description":         "Course generated from provided content.",
            "level":               level,
            "estimated_duration":  "1-2 hours",
            "learning_objectives": ["Understand the key concepts"],
            "modules":             []
        }
    return result


# ── 2. Generate quiz questions ────────────────────────────────────────────────

def generate_quiz(
    module_content: str,
    module_title:   str,
    num_mcq:        int = 5,
    num_open:       int = 2
) -> dict:
    """
    Generate quiz questions for a module.
    Returns { module_title, mcq_questions, open_questions }
    """
    prompt = (
        f"You are an expert quiz designer.\n"
        f"Create quiz questions for this module: {module_title}\n\n"
        f"MODULE CONTENT:\n{module_content[:3000]}\n\n"
        f"Generate:\n"
        f"- {num_mcq} multiple choice questions (4 options each)\n"
        f"- {num_open} open-ended questions\n\n"
        f"Make questions test genuine understanding, not just memorisation.\n"
        f"Mix difficulty: easy (40%), medium (40%), hard (20%).\n\n"
        f"Respond in EXACT JSON:\n"
        f"{FENCE}json\n"
        "{\n"
        '  "module_title": "...",\n'
        '  "mcq_questions": [\n'
        "    {\n"
        '      "id": 1,\n'
        '      "question": "...",\n'
        '      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},\n'
        '      "correct_answer": "A",\n'
        '      "explanation": "Why A is correct",\n'
        '      "difficulty": "Easy"\n'
        "    }\n"
        "  ],\n"
        '  "open_questions": [\n'
        "    {\n"
        '      "id": 1,\n'
        '      "question": "...",\n'
        '      "model_answer": "What a good answer should include",\n'
        '      "marks": 5\n'
        "    }\n"
        "  ]\n"
        "}\n"
        f"{FENCE}"
    )

    raw    = call_llm(prompt, max_tokens=2048)
    result = parse_json(raw)

    if not result:
        return {
            "module_title":    module_title,
            "mcq_questions":   [],
            "open_questions":  []
        }
    return result


# ── 3. Auto-grade quiz ────────────────────────────────────────────────────────

def grade_mcq(
    questions:    list[dict],
    user_answers: dict[int, str]
) -> dict:
    """
    Grade MCQ answers and return detailed results.
    user_answers: { question_id: "A" }
    """
    results   = []
    correct   = 0
    total     = len(questions)

    for q in questions:
        qid        = q["id"]
        user_ans   = user_answers.get(qid, "")
        correct_ans = q["correct_answer"]
        is_correct = user_ans.upper() == correct_ans.upper()

        if is_correct:
            correct += 1

        results.append({
            "id":           qid,
            "question":     q["question"],
            "user_answer":  user_ans,
            "correct_answer": correct_ans,
            "is_correct":   is_correct,
            "explanation":  q.get("explanation", ""),
            "options":      q.get("options", {})
        })

    score_pct = round((correct / total * 100)) if total > 0 else 0

    return {
        "score":       correct,
        "total":       total,
        "percentage":  score_pct,
        "results":     results,
        "grade":       (
            "Excellent" if score_pct >= 90 else
            "Good"      if score_pct >= 75 else
            "Pass"      if score_pct >= 60 else
            "Needs improvement"
        )
    }


def grade_open_answer(
    question:     str,
    model_answer: str,
    user_answer:  str,
    max_marks:    int = 5
) -> dict:
    """Use Qwen to evaluate an open-ended answer."""
    prompt = (
        f"You are a fair and constructive examiner grading a student's answer.\n\n"
        f"QUESTION: {question}\n\n"
        f"MODEL ANSWER (what a good answer should include):\n{model_answer}\n\n"
        f"STUDENT'S ANSWER:\n{user_answer}\n\n"
        f"Maximum marks: {max_marks}\n\n"
        f"Grade the answer and respond in JSON:\n"
        f"{FENCE}json\n"
        "{\n"
        '  "marks_awarded": 3,\n'
        '  "percentage": 60,\n'
        '  "feedback": "What the student did well and what is missing",\n'
        '  "strengths": ["strength 1"],\n'
        '  "improvements": ["what to add or improve"]\n'
        "}\n"
        f"{FENCE}"
    )

    raw    = call_llm(prompt, max_tokens=512)
    result = parse_json(raw)

    if not result:
        return {
            "marks_awarded": max_marks // 2,
            "percentage":    50,
            "feedback":      "Answer partially addresses the question.",
            "strengths":     [],
            "improvements":  ["Provide more detail"]
        }
    return result


# ── 4. Adaptive follow-up ─────────────────────────────────────────────────────

def generate_followup(
    module_content: str,
    score_pct:      int,
    wrong_topics:   list[str]
) -> str:
    """
    Generate adaptive follow-up content based on quiz performance.
    Low score → simplified re-explanation + easier examples.
    High score → advanced extension content.
    """
    if score_pct >= 80:
        prompt = (
            f"The student scored {score_pct}% on this module. Excellent performance!\n\n"
            f"MODULE CONTENT:\n{module_content[:2000]}\n\n"
            f"Generate ADVANCED extension content that:\n"
            f"- Goes deeper into the topic\n"
            f"- Introduces related advanced concepts\n"
            f"- Provides a challenging real-world application\n"
            f"- Suggests further reading or projects\n\n"
            f"Keep it engaging and challenging."
        )
    else:
        wrong_text = ", ".join(wrong_topics) if wrong_topics else "several concepts"
        prompt = (
            f"The student scored {score_pct}% on this module and struggled with: {wrong_text}\n\n"
            f"MODULE CONTENT:\n{module_content[:2000]}\n\n"
            f"Generate REMEDIAL content that:\n"
            f"- Re-explains the difficult concepts more simply\n"
            f"- Uses analogies and everyday examples\n"
            f"- Breaks complex ideas into smaller steps\n"
            f"- Ends with 3 easier practice questions\n\n"
            f"Be encouraging and patient in tone."
        )

    return call_llm(prompt, max_tokens=1024)


# ── 5. Study chat ─────────────────────────────────────────────────────────────

def answer_study_question(
    question:       str,
    course_content: str,
    chat_history:   list[dict] = None
) -> str:
    """Answer a student's question about the course material."""
    history_text = ""
    if chat_history:
        for msg in (chat_history or [])[-4:]:
            role          = "Student" if msg["role"] == "user" else "Tutor"
            history_text += f"{role}: {msg['content']}\n\n"

    prompt = (
        f"You are a patient and knowledgeable tutor.\n"
        f"Answer the student's question based on the course material below.\n"
        f"Use simple language, examples, and analogies where helpful.\n\n"
        f"COURSE MATERIAL:\n{course_content[:3000]}\n\n"
        f"{f'CONVERSATION HISTORY:{chr(10)}{history_text}' if history_text else ''}\n"
        f"Student: {question}\n\n"
        f"Tutor:"
    )

    return call_llm(prompt, max_tokens=512)