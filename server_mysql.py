#!/usr/bin/env python3
"""
Stable Hire MySQL-only backend.

This backend is intentionally standalone: it does not import server.py and does
not depend on SQLite or Excel. It serves the static frontend and exposes:

GET  /api/state   -> read MySQL, recompute utilities/matching, persist results
POST /api/state   -> save posted state into MySQL, recompute, return payload
POST /api/reset   -> re-import mysql_seed.sql, recompute, return payload

Requirements:
- Python 3.9+
- MySQL command line client available as `mysql`
- A MySQL user that can access/create the stable_hire database
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8000"))
MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
MYSQL_USER = os.environ.get("MYSQL_USER", "stable_user")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "stable_pass")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "stable_hire")

SCHEMA_PATH = BASE_DIR / "mysql_schema.sql"
SEED_PATH = BASE_DIR / "mysql_seed.sql"

STUDENT_ATTRS = [
    {"key": "gpa", "label": "学历与成绩", "min": 0, "max": 4},
    {"key": "internship", "label": "实习/项目", "min": 0, "max": 5},
    {"key": "skills", "label": "技能/证书", "min": 0, "max": 5},
    {"key": "personality", "label": "个性特质", "min": 0, "max": 1},
    {"key": "soft", "label": "软技能", "min": 0, "max": 1},
]

COMPANY_ATTRS = [
    {"key": "salary", "label": "薪资回报", "min": 3000, "max": 15000},
    {"key": "location", "label": "地点/远程", "min": 0, "max": 1},
    {"key": "career", "label": "成长机会", "min": 0, "max": 1},
    {"key": "reputation", "label": "公司声誉", "min": 0, "max": 1},
    {"key": "meaning", "label": "岗位匹配", "min": 0, "max": 1},
]

STUDENT_PREF_KEYS = ["salary", "location", "career", "reputation", "meaning"]
COMPANY_PREF_KEYS = ["gpa", "skills", "internship", "personality", "soft"]


def mysql_command(skip_column_names: bool = False, database: Optional[str] = MYSQL_DATABASE) -> List[str]:
    command = [
        "mysql",
        "-h",
        MYSQL_HOST,
        "-P",
        MYSQL_PORT,
        "-u",
        MYSQL_USER,
        "--default-character-set=utf8mb4",
        "--batch",
        "--raw",
    ]
    if skip_column_names:
        command.append("-N")
    if database:
        command.append(database)
    return command


def run_mysql(sql: str, skip_column_names: bool = False, database: Optional[str] = MYSQL_DATABASE) -> str:
    env = os.environ.copy()
    env["MYSQL_PWD"] = MYSQL_PASSWORD
    result = subprocess.run(
        mysql_command(skip_column_names=skip_column_names, database=database),
        input=sql,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Unknown MySQL error"
        raise RuntimeError(message)
    return result.stdout


def execute_sql_file(path: Path, database: Optional[str] = MYSQL_DATABASE) -> None:
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    run_mysql(path.read_text(encoding="utf-8"), database=database)


def ensure_database() -> None:
    """Create schema if needed. Seed the database only when it is empty."""
    if SCHEMA_PATH.exists():
        # mysql_schema.sql contains CREATE DATABASE and USE stable_hire, so do not
        # connect to a database that might not exist yet.
        execute_sql_file(SCHEMA_PATH, database=None)
    ensure_optional_columns()

    count_output = run_mysql("SELECT COUNT(*) FROM workers;", skip_column_names=True)
    worker_count = int((count_output.strip() or "0").splitlines()[0])
    if worker_count == 0 and SEED_PATH.exists():
        execute_sql_file(SEED_PATH, database=MYSQL_DATABASE)


def ensure_optional_columns() -> None:
    """Migrate older local databases without requiring users to rebuild MySQL."""
    migrations = [
        ("worker_profiles", "school_text", "ALTER TABLE worker_profiles ADD COLUMN school_text TEXT AFTER worker_id;"),
        ("worker_profiles", "gpa_text", "ALTER TABLE worker_profiles ADD COLUMN gpa_text TEXT AFTER school_text;"),
        ("worker_profiles", "major_text", "ALTER TABLE worker_profiles ADD COLUMN major_text TEXT AFTER gpa_text;"),
        ("worker_profiles", "course_text", "ALTER TABLE worker_profiles ADD COLUMN course_text TEXT AFTER major_text;"),
        ("employer_profiles", "salary_text", "ALTER TABLE employer_profiles ADD COLUMN salary_text TEXT AFTER employer_id;"),
    ]
    for table, column, sql in migrations:
        exists = run_mysql(f"SHOW COLUMNS FROM {table} LIKE {sql_string(column)};", skip_column_names=True)
        if not exists.strip():
            run_mysql(sql)


def sql_string(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def sql_number(value: Any) -> str:
    if value is None or value == "":
        return "NULL"
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return "0"


def insert(table: str, columns: Iterable[str], values: Iterable[str]) -> str:
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(values)});"


def clamp_score(value: Any, minimum: float, maximum: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = minimum
    return max(minimum, min(maximum, numeric))


def merged_text(*parts: Any) -> str:
    return " ".join(str(part or "") for part in parts).lower()


def keyword_score(text: str, keyword_weights: Dict[str, float], maximum: float) -> float:
    score = 0.0
    for keyword, weight in keyword_weights.items():
        if keyword.lower() in text:
            score += weight
    return clamp_score(score, 0, maximum)


def parse_gpa(text: str, fallback: float = 2.0) -> float:
    """Extract a concrete GPA from text. A single student should not store a GPA range."""
    normalized = text.lower()
    match = re.search(r"(?:gpa|绩点)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*/\s*4(?:\.0)?", normalized)
    if match:
        return clamp_score(match.group(1), 0, 4)
    match = re.search(r"(?:gpa|绩点)\s*[:：]?\s*(\d+(?:\.\d+)?)", normalized)
    if match:
        return clamp_score(match.group(1), 0, 4)
    match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*4(?:\.0)?", normalized)
    if match:
        return clamp_score(match.group(1), 0, 4)
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", normalized)
    if match:
        return clamp_score(match.group(1), 0, 4)
    return clamp_score(fallback, 0, 4)


def split_education_text(text: str) -> Dict[str, str]:
    """Backfill old seed rows into the newer GPA / major / course fields."""
    source = str(text or "").strip()
    if not source:
        return {"gpaText": "", "majorText": "", "courseText": ""}

    gpa_text = ""
    gpa_match = re.search(r"(?:GPA|绩点)?\s*(\d+(?:\.\d+)?)\s*/\s*4(?:\.0)?", source, flags=re.IGNORECASE)
    if gpa_match:
        gpa_text = f"GPA {gpa_match.group(1)}/4.0"

    major_text = ""
    major_match = re.search(r"[，,]\s*([^，,。；;]+?)\s*专业", source)
    if major_match:
        major_text = major_match.group(1).strip()

    course_text = ""
    course_match = re.search(r"相关课程(?:包括|有)?\s*([^。；;]+)", source)
    if course_match:
        course_text = course_match.group(1).strip(" ：:，,。")

    return {"gpaText": gpa_text, "majorText": major_text, "courseText": course_text}


def default_salary_text(value: Any) -> str:
    try:
        salary = int(round(float(value or 0)))
    except (TypeError, ValueError):
        salary = 0
    if salary <= 0:
        return ""
    if salary >= 1000:
        return f"月薪约 {salary // 1000}k，具体福利以企业公示为准。"
    return f"薪资约 {salary} 元，具体福利以企业公示为准。"


def parse_months(text: str) -> float:
    months = 0.0
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*个?月", text):
        months += float(match.group(1))
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*months?", text.lower()):
        months += float(match.group(1))
    return months


def infer_capability_signal(profile: Dict[str, str], current: Dict[str, Any]) -> float:
    text = merged_text(
        profile.get("gpaText"),
        profile.get("schoolText"),
        profile.get("majorText"),
        profile.get("courseText"),
        profile.get("educationText"),
    )
    return parse_gpa(text, fallback=float(current.get("gpa", 2.0) or 2.0))


def infer_skills(profile: Dict[str, str], current: Dict[str, Any]) -> float:
    text = merged_text(
        profile.get("skillsText"),
        profile.get("internshipText"),
        profile.get("courseText"),
        profile.get("majorText"),
        profile.get("educationText"),
    )
    if not text.strip():
        return clamp_score(current.get("skills", 1.0), 0, 5)
    weights = {
        "python": 0.75,
        "sql": 0.75,
        "java": 0.55,
        "javascript": 0.55,
        "excel": 0.35,
        "tableau": 0.45,
        "power bi": 0.45,
        "machine learning": 0.70,
        "机器学习": 0.70,
        "数据分析": 0.60,
        "data analysis": 0.60,
        "建模": 0.55,
        "modeling": 0.55,
        "算法": 0.45,
        "automation": 0.45,
        "自动化": 0.45,
        "project": 0.35,
        "项目": 0.35,
        "certificate": 0.35,
        "证书": 0.35,
        "cet-6": 0.25,
        "英语六级": 0.25,
    }
    # A small base score avoids treating every brief profile as zero-capability.
    return clamp_score(0.4 + keyword_score(text, weights, 4.8), 0, 5)


def infer_internship(profile: Dict[str, str], current: Dict[str, Any]) -> float:
    text = merged_text(profile.get("internshipText"), profile.get("skillsText"))
    if not text.strip():
        return clamp_score(current.get("internship", 0.5), 0, 5)
    months = parse_months(text)
    if months >= 9:
        month_score = 3.8
    elif months >= 6:
        month_score = 3.2
    elif months >= 3:
        month_score = 2.4
    elif months > 0:
        month_score = 1.4
    else:
        month_score = 0.4
    weights = {
        "实习": 0.35,
        "intern": 0.35,
        "project": 0.40,
        "项目": 0.40,
        "数据分析": 0.35,
        "analysis": 0.30,
        "产品": 0.25,
        "运营": 0.25,
        "研发": 0.35,
        "research": 0.30,
        "用户增长": 0.25,
        "sales forecasting": 0.30,
        "风控": 0.25,
    }
    return clamp_score(month_score + keyword_score(text, weights, 1.6), 0, 5)


def infer_personality(profile: Dict[str, str], current: Dict[str, Any]) -> float:
    text = merged_text(profile.get("personalityText"))
    if not text.strip():
        return clamp_score(current.get("personality", 0.5), 0, 1)
    positive = {
        "主动": 0.15,
        "责任": 0.15,
        "稳定": 0.12,
        "抗压": 0.12,
        "目标感": 0.10,
        "自驱": 0.12,
        "自律": 0.10,
        "适应": 0.10,
        "成熟": 0.10,
        "proactive": 0.12,
        "responsible": 0.12,
    }
    negative = {
        "不足": -0.14,
        "偏弱": -0.14,
        "不够": -0.10,
        "需要提升": -0.12,
        "需要加强": -0.12,
    }
    score = 0.45 + keyword_score(text, positive, 0.55)
    for keyword, penalty in negative.items():
        if keyword in text:
            score += penalty
    return clamp_score(score, 0, 1)


def infer_soft_skills(profile: Dict[str, str], current: Dict[str, Any]) -> float:
    text = merged_text(profile.get("softText"), profile.get("internshipText"))
    if not text.strip():
        return clamp_score(current.get("soft", 0.45), 0, 1)
    positive = {
        "沟通": 0.15,
        "表达": 0.12,
        "协作": 0.15,
        "团队": 0.12,
        "汇报": 0.10,
        "领导": 0.10,
        "协调": 0.10,
        "presentation": 0.10,
        "team": 0.10,
        "communication": 0.12,
        "leader": 0.10,
    }
    negative = {
        "不足": -0.14,
        "偏弱": -0.14,
        "需要提升": -0.12,
        "需要加强": -0.12,
    }
    score = 0.40 + keyword_score(text, positive, 0.60)
    for keyword, penalty in negative.items():
        if keyword in text:
            score += penalty
    return clamp_score(score, 0, 1)


def infer_worker_scores(profile: Dict[str, str], current: Dict[str, Any]) -> Dict[str, float]:
    """Convert raw student profile text into algorithm-ready numeric scores."""
    return {
        "gpa": round(infer_capability_signal(profile, current), 3),
        "skills": round(infer_skills(profile, current), 3),
        "internship": round(infer_internship(profile, current), 3),
        "personality": round(infer_personality(profile, current), 3),
        "soft": round(infer_soft_skills(profile, current), 3),
    }


def parse_salary(text: str, fallback: float = 9000.0) -> float:
    normalized = text.lower().replace(",", "")
    values: List[float] = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*[kK]", normalized):
        values.append(float(match.group(1)) * 1000)
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*万", normalized):
        values.append(float(match.group(1)) * 10000)
    for match in re.finditer(r"(\d{4,5})\s*(?:元|rmb|cny)?", normalized):
        values.append(float(match.group(1)))
    if values:
        return clamp_score(sum(values) / len(values), 3000, 15000)
    return clamp_score(fallback, 3000, 15000)


def score_text_dimension(text: str, positive: Dict[str, float], negative: Optional[Dict[str, float]] = None, base: float = 0.45) -> float:
    score = base + keyword_score(text, positive, 0.70)
    for keyword, penalty in (negative or {}).items():
        if keyword.lower() in text:
            score += penalty
    return clamp_score(score, 0, 1)


def infer_company_scores(profile: Dict[str, str], current: Dict[str, Any]) -> Dict[str, float]:
    location_text = merged_text(profile.get("locationText"))
    career_text = merged_text(profile.get("careerText"), profile.get("meaningText"))
    reputation_text = merged_text(profile.get("reputationText"))
    meaning_text = merged_text(profile.get("meaningText"), profile.get("candidateText"))

    return {
        "salary": round(parse_salary(profile.get("salaryText", ""), fallback=float(current.get("salary", 9000) or 9000)), 3),
        "location": round(
            score_text_dimension(
                location_text,
                {
                    "远程": 0.25,
                    "remote": 0.25,
                    "混合": 0.16,
                    "核心": 0.14,
                    "一线": 0.14,
                    "北京": 0.12,
                    "上海": 0.12,
                    "深圳": 0.12,
                    "杭州": 0.10,
                    "广州": 0.10,
                    "交通便利": 0.12,
                },
                {"出差": -0.12, "线下": -0.08, "不固定": -0.10},
            ),
            3,
        ),
        "career": round(
            score_text_dimension(
                career_text,
                {
                    "成长": 0.16,
                    "晋升": 0.16,
                    "培训": 0.14,
                    "导师": 0.14,
                    "轮岗": 0.12,
                    "核心项目": 0.14,
                    "学习": 0.10,
                    "发展": 0.12,
                    "快": 0.08,
                },
                {"不确定": -0.12, "有限": -0.14},
            ),
            3,
        ),
        "reputation": round(
            score_text_dimension(
                reputation_text,
                {
                    "头部": 0.22,
                    "领先": 0.18,
                    "知名": 0.16,
                    "大型": 0.14,
                    "上市": 0.14,
                    "全球": 0.16,
                    "品牌": 0.12,
                    "稳定": 0.10,
                    "行业声誉": 0.16,
                },
                {"早期": -0.06, "不确定": -0.12},
            ),
            3,
        ),
        "meaning": round(
            score_text_dimension(
                meaning_text,
                {
                    "数据": 0.12,
                    "算法": 0.12,
                    "产品": 0.10,
                    "增长": 0.10,
                    "研究": 0.10,
                    "业务挑战": 0.14,
                    "核心": 0.12,
                    "专业相关": 0.14,
                    "创新": 0.10,
                    "ai": 0.10,
                    "python": 0.08,
                    "sql": 0.08,
                },
                {"重复": -0.08, "基础": -0.06},
            ),
            3,
        ),
    }


def infer_weights_from_text(text: str, keys: List[str], keyword_groups: Dict[str, Dict[str, float]], fallback: Dict[str, Any]) -> Dict[str, float]:
    if not text.strip():
        return normalize_vector(fallback, keys)
    normalized = text.lower()
    raw = {key: 1.0 for key in keys}
    for key in keys:
        raw[key] += keyword_score(normalized, keyword_groups.get(key, {}), 4.0)
        if key.lower() in normalized:
            raw[key] += 1.2
    if any(word in normalized for word in ["最看重", "优先", "核心", "重点"]):
        for key in keys:
            if raw[key] > 1.0:
                raw[key] *= 1.25
    return normalize_vector(raw, keys)


STUDENT_PREF_KEYWORDS = {
    "salary": {"薪资": 1.4, "工资": 1.2, "待遇": 1.1, "高薪": 1.4, "收入": 1.1, "福利": 0.8, "salary": 1.4},
    "location": {"地点": 1.2, "城市": 1.0, "通勤": 1.0, "远程": 1.3, "上海": 0.8, "北京": 0.8, "深圳": 0.8, "location": 1.2},
    "career": {"成长": 1.4, "晋升": 1.2, "培训": 1.0, "学习": 0.9, "发展": 1.1, "导师": 0.9, "career": 1.2},
    "reputation": {"声誉": 1.2, "品牌": 1.1, "大厂": 1.3, "头部": 1.2, "稳定": 0.9, "知名": 0.9, "reputation": 1.2},
    "meaning": {"岗位": 0.9, "匹配": 1.2, "兴趣": 1.0, "价值": 0.9, "意义": 1.1, "专业相关": 1.1, "meaning": 1.2},
}


COMPANY_PREF_KEYWORDS = {
    "gpa": {"学历": 1.2, "成绩": 1.2, "gpa": 1.3, "绩点": 1.3, "学校": 1.0, "专业": 0.9, "课程": 0.8},
    "skills": {"技能": 1.3, "证书": 1.0, "python": 1.0, "sql": 1.0, "java": 0.8, "建模": 0.8, "数据分析": 0.9},
    "internship": {"实习": 1.3, "项目": 1.1, "经验": 1.0, "落地": 0.9, "业务": 0.8, "作品": 0.8},
    "personality": {"个性": 1.0, "主动": 1.2, "责任": 1.1, "稳定": 1.0, "抗压": 1.0, "自驱": 1.1},
    "soft": {"软技能": 1.3, "沟通": 1.2, "协作": 1.1, "表达": 1.0, "团队": 0.9, "领导": 0.9},
}


def apply_text_inference(state: Dict[str, Any]) -> Dict[str, Any]:
    """Convert submitted descriptions into the numeric fields used by matching."""
    for student in state.get("students", []):
        sid = student.get("id")
        if not sid:
            continue
        profile = state.get("studentProfiles", {}).get(sid, default_student_profile())
        student.update(infer_worker_scores(profile, student))
        state["studentWeights"][sid] = infer_weights_from_text(
            merged_text(profile.get("preferenceText")),
            STUDENT_PREF_KEYS,
            STUDENT_PREF_KEYWORDS,
            state.get("studentWeights", {}).get(sid, {}),
        )
    for company in state.get("companies", []):
        cid = company.get("id")
        if not cid:
            continue
        profile = state.get("companyProfiles", {}).get(cid, default_company_profile())
        company.update(infer_company_scores(profile, company))
        state["companyWeights"][cid] = infer_weights_from_text(
            merged_text(profile.get("candidateText")),
            COMPANY_PREF_KEYS,
            COMPANY_PREF_KEYWORDS,
            state.get("companyWeights", {}).get(cid, {}),
        )
    return state


def rows(sql: str) -> List[List[Optional[str]]]:
    output = run_mysql(sql, skip_column_names=True)
    parsed: List[List[Optional[str]]] = []
    for line in output.splitlines():
        parsed.append([None if item == "NULL" else item for item in line.split("\t")])
    return parsed


def normalize_vector(values: Dict[str, Any], keys: List[str]) -> Dict[str, float]:
    total = sum(float(values.get(key, 0) or 0) for key in keys)
    if total <= 0:
        equal = 1 / len(keys) if keys else 0
        return {key: equal for key in keys}
    return {key: float(values.get(key, 0) or 0) / total for key in keys}


def default_student_profile() -> Dict[str, str]:
    return {
        "schoolText": "",
        "gpaText": "",
        "majorText": "",
        "courseText": "",
        "educationText": "",
        "internshipText": "",
        "skillsText": "",
        "personalityText": "",
        "softText": "",
        "preferenceText": "",
    }


def default_company_profile() -> Dict[str, str]:
    return {
        "salaryText": "",
        "locationText": "",
        "careerText": "",
        "reputationText": "",
        "meaningText": "",
        "candidateText": "",
    }


def ensure_state_defaults(state: Dict[str, Any]) -> Dict[str, Any]:
    state.setdefault("students", [])
    state.setdefault("companies", [])
    state.setdefault("studentWeights", {})
    state.setdefault("companyWeights", {})
    state.setdefault("studentProfiles", {})
    state.setdefault("companyProfiles", {})

    for student in state["students"]:
        sid = student["id"]
        for attr in STUDENT_ATTRS:
            student[attr["key"]] = float(student.get(attr["key"], 0) or 0)
        state["studentWeights"][sid] = normalize_vector(
            state["studentWeights"].get(sid, {}), STUDENT_PREF_KEYS
        )
        profile = default_student_profile()
        profile.update(state["studentProfiles"].get(sid, {}) or {})
        state["studentProfiles"][sid] = profile

    for company in state["companies"]:
        cid = company["id"]
        for attr in COMPANY_ATTRS:
            company[attr["key"]] = float(company.get(attr["key"], 0) or 0)
        state["companyWeights"][cid] = normalize_vector(
            state["companyWeights"].get(cid, {}), COMPANY_PREF_KEYS
        )
        profile = default_company_profile()
        profile.update(state["companyProfiles"].get(cid, {}) or {})
        state["companyProfiles"][cid] = profile

    return state


def load_state() -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "students": [],
        "companies": [],
        "studentWeights": {},
        "companyWeights": {},
        "studentProfiles": {},
        "companyProfiles": {},
    }

    for row in rows(
        """
        SELECT id, name, capability_signal, internship_history, skills, personality, soft_skills
        FROM workers
        ORDER BY id;
        """
    ):
        state["students"].append(
            {
                "id": row[0],
                "name": row[1] or row[0],
                "gpa": float(row[2] or 0),
                "internship": float(row[3] or 0),
                "skills": float(row[4] or 0),
                "personality": float(row[5] or 0),
                "soft": float(row[6] or 0),
            }
        )

    for row in rows(
        """
        SELECT id, name, salary_reward, location_remote, growth_opportunity, reputation, skill_fit_meaning
        FROM employers
        ORDER BY id;
        """
    ):
        state["companies"].append(
            {
                "id": row[0],
                "name": row[1] or row[0],
                "salary": float(row[2] or 0),
                "location": float(row[3] or 0),
                "career": float(row[4] or 0),
                "reputation": float(row[5] or 0),
                "meaning": float(row[6] or 0),
            }
        )

    for row in rows(
        """
        SELECT worker_id, salary_reward, location_remote, growth_opportunity, reputation, skill_fit_meaning
        FROM worker_preferences
        ORDER BY worker_id;
        """
    ):
        state["studentWeights"][row[0]] = {
            "salary": float(row[1] or 0),
            "location": float(row[2] or 0),
            "career": float(row[3] or 0),
            "reputation": float(row[4] or 0),
            "meaning": float(row[5] or 0),
        }

    for row in rows(
        """
        SELECT employer_id, capability_signal, skills, internship_history, personality, soft_skills
        FROM employer_preferences
        ORDER BY employer_id;
        """
    ):
        state["companyWeights"][row[0]] = {
            "gpa": float(row[1] or 0),
            "skills": float(row[2] or 0),
            "internship": float(row[3] or 0),
            "personality": float(row[4] or 0),
            "soft": float(row[5] or 0),
        }

    for row in rows(
        """
        SELECT worker_id, school_text, gpa_text, major_text, course_text, education_text, internship_text, skills_text, personality_text, soft_text, preference_text
        FROM worker_profiles
        ORDER BY worker_id;
        """
    ):
        split = split_education_text(row[5] or "")
        state["studentProfiles"][row[0]] = {
            "schoolText": row[1] or "",
            "gpaText": row[2] or split["gpaText"],
            "majorText": row[3] or split["majorText"],
            "courseText": row[4] or split["courseText"],
            "educationText": row[5] or "",
            "internshipText": row[6] or "",
            "skillsText": row[7] or "",
            "personalityText": row[8] or "",
            "softText": row[9] or "",
            "preferenceText": row[10] or "",
        }

    for row in rows(
        """
        SELECT employer_id, salary_text, location_text, career_text, reputation_text, meaning_text, candidate_text
        FROM employer_profiles
        ORDER BY employer_id;
        """
    ):
        company = next((item for item in state["companies"] if item["id"] == row[0]), {})
        state["companyProfiles"][row[0]] = {
            "salaryText": row[1] or default_salary_text(company.get("salary")),
            "locationText": row[2] or "",
            "careerText": row[3] or "",
            "reputationText": row[4] or "",
            "meaningText": row[5] or "",
            "candidateText": row[6] or "",
        }

    return ensure_state_defaults(state)


def normalize_value(value: Any, attr: Dict[str, Any]) -> float:
    minimum = float(attr["min"])
    maximum = float(attr["max"])
    if maximum == minimum:
        return 0.0
    raw = float(value or 0)
    normalized = (raw - minimum) / (maximum - minimum)
    return max(0.0, min(1.0, normalized))


def score_entity(entity: Dict[str, Any], attrs: List[Dict[str, Any]], weights: Dict[str, Any]) -> float:
    weight_keys = [attr["key"] for attr in attrs]
    normalized_weights = normalize_vector(weights, weight_keys)
    return sum(
        normalized_weights[attr["key"]] * normalize_value(entity.get(attr["key"]), attr)
        for attr in attrs
    )


def calculate_utilities(state: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, float]]]:
    student_utilities: Dict[str, Dict[str, float]] = {}
    company_utilities: Dict[str, Dict[str, float]] = {}

    for student in state["students"]:
        sid = student["id"]
        student_utilities[sid] = {}
        student_weights = state["studentWeights"].get(sid, {})
        for company in state["companies"]:
            cid = company["id"]
            student_utilities[sid][cid] = round(score_entity(company, COMPANY_ATTRS, student_weights), 6)

    for company in state["companies"]:
        cid = company["id"]
        company_utilities[cid] = {}
        company_weights = state["companyWeights"].get(cid, {})
        for student in state["students"]:
            sid = student["id"]
            company_utilities[cid][sid] = round(score_entity(student, STUDENT_ATTRS, company_weights), 6)

    return {"studentUtilities": student_utilities, "companyUtilities": company_utilities}


def build_preferences(state: Dict[str, Any], utilities: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
    student_prefs: Dict[str, List[str]] = {}
    company_prefs: Dict[str, List[str]] = {}

    for student in state["students"]:
        sid = student["id"]
        student_prefs[sid] = [
            company["id"]
            for company in sorted(
                state["companies"],
                key=lambda item: (utilities["studentUtilities"].get(sid, {}).get(item["id"], 0), item["id"]),
                reverse=True,
            )
        ]

    for company in state["companies"]:
        cid = company["id"]
        company_prefs[cid] = [
            student["id"]
            for student in sorted(
                state["students"],
                key=lambda item: (utilities["companyUtilities"].get(cid, {}).get(item["id"], 0), item["id"]),
                reverse=True,
            )
        ]

    return {"studentPrefs": student_prefs, "companyPrefs": company_prefs}


def gale_shapley(state: Dict[str, Any], prefs: Dict[str, Dict[str, List[str]]]) -> Dict[str, Any]:
    free = [student["id"] for student in state["students"]]
    next_choice = {student["id"]: 0 for student in state["students"]}
    held_by_company: Dict[str, str] = {}
    rounds: List[Dict[str, Any]] = []

    company_rank = {
        company["id"]: {
            student_id: index
            for index, student_id in enumerate(prefs["companyPrefs"].get(company["id"], []))
        }
        for company in state["companies"]
    }

    while any(next_choice[student_id] < len(state["companies"]) for student_id in free):
        proposals: Dict[str, List[str]] = {}
        active = [student_id for student_id in free if next_choice[student_id] < len(state["companies"])]
        free = []

        for student_id in active:
            company_id = prefs["studentPrefs"].get(student_id, [])[next_choice[student_id]]
            next_choice[student_id] += 1
            proposals.setdefault(company_id, []).append(student_id)

        decisions = []
        for company in state["companies"]:
            company_id = company["id"]
            applicants = list(proposals.get(company_id, []))
            if company_id in held_by_company:
                applicants.append(held_by_company[company_id])
            if not applicants:
                continue

            applicants.sort(key=lambda student_id: company_rank[company_id].get(student_id, 10**9))
            accepted = applicants[0]
            rejected = applicants[1:]
            held_by_company[company_id] = accepted
            free.extend(rejected)
            decisions.append(
                {
                    "companyId": company_id,
                    "applicants": applicants,
                    "accepted": accepted,
                    "rejected": rejected,
                }
            )

        rounds.append(
            {
                "number": len(rounds) + 1,
                "proposals": proposals,
                "decisions": decisions,
                "held": dict(held_by_company),
            }
        )

        if not decisions and not free:
            break

    return {"heldByCompany": held_by_company, "rounds": rounds}


def find_blocking_pairs(
    state: Dict[str, Any], prefs: Dict[str, Dict[str, List[str]]], matches: Dict[str, str]
) -> List[Dict[str, str]]:
    current_company_by_student = {
        student_id: company_id for company_id, student_id in matches.items() if student_id
    }
    company_rank = {
        company["id"]: {
            student_id: index
            for index, student_id in enumerate(prefs["companyPrefs"].get(company["id"], []))
        }
        for company in state["companies"]
    }

    pairs: List[Dict[str, str]] = []
    for student in state["students"]:
        student_id = student["id"]
        student_list = prefs["studentPrefs"].get(student_id, [])
        current_company = current_company_by_student.get(student_id)
        current_index = student_list.index(current_company) if current_company in student_list else len(student_list)

        for company_id in student_list[:current_index]:
            current_student = matches.get(company_id)
            if current_student is None or company_rank[company_id].get(student_id, 10**9) < company_rank[company_id].get(current_student, 10**9):
                pairs.append({"studentId": student_id, "companyId": company_id})

    return pairs


def calculate_metrics(
    state: Dict[str, Any], utilities: Dict[str, Any], matches: Dict[str, str], blocking_pairs: List[Dict[str, str]]
) -> Dict[str, float]:
    matched = [(company_id, student_id) for company_id, student_id in matches.items() if student_id]
    denominator = len(matched) or 1
    student_score = sum(utilities["studentUtilities"][student_id][company_id] for company_id, student_id in matched)
    company_score = sum(utilities["companyUtilities"][company_id][student_id] for company_id, student_id in matched)
    total_students = len(state["students"]) or 1

    return {
        "successRate": round(len(matched) / total_students, 6),
        "studentAvg": round(student_score / denominator, 6),
        "companyAvg": round(company_score / denominator, 6),
        "totalUtility": round(student_score + company_score, 6),
        "blockingPairs": len(blocking_pairs),
    }


def compute_result(state: Dict[str, Any]) -> Dict[str, Any]:
    state = ensure_state_defaults(state)
    utilities = calculate_utilities(state)
    prefs = build_preferences(state, utilities)
    matching = gale_shapley(state, prefs)
    blocking_pairs = find_blocking_pairs(state, prefs, matching["heldByCompany"])
    metrics = calculate_metrics(state, utilities, matching["heldByCompany"], blocking_pairs)
    return {
        **utilities,
        "prefs": prefs,
        **matching,
        "blockingPairs": blocking_pairs,
        "metrics": metrics,
    }


def entity_type(entity_id: str, ai_value: str, human_value: str) -> str:
    return ai_value if str(entity_id).startswith("AI") else human_value


def audit_values(entity_id: str, role: str) -> Tuple[float, float, float]:
    trust = 0.82 if str(entity_id).startswith("AI") else (0.76 if role == "employer" else 0.75)
    audit_probability = round(0.15 + (1 - trust) * 0.6, 3)
    deposit = round(1000 + (1 - trust) * 5000, 2)
    penalty = round(deposit * 1.8 + audit_probability * 3000, 2)
    return audit_probability, deposit, penalty


def build_save_sql(state: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    state = apply_text_inference(ensure_state_defaults(state))
    result = compute_result(state)
    student_utilities = result["studentUtilities"]
    company_utilities = result["companyUtilities"]

    lines = [
        "SET FOREIGN_KEY_CHECKS = 0;",
        "DELETE FROM audit_records;",
        "DELETE FROM algorithm_rounds;",
        "DELETE FROM matching_results;",
        "DELETE FROM utility_scores;",
        "DELETE FROM worker_preferences;",
        "DELETE FROM employer_preferences;",
        "DELETE FROM worker_profiles;",
        "DELETE FROM employer_profiles;",
        "DELETE FROM workers;",
        "DELETE FROM employers;",
        "SET FOREIGN_KEY_CHECKS = 1;",
        "",
    ]

    for worker in state["students"]:
        worker_id = worker["id"]
        profile = state["studentProfiles"].get(worker_id, default_student_profile())
        weights = state["studentWeights"].get(worker_id, {})
        lines.append(
            insert(
                "workers",
                [
                    "id",
                    "name",
                    "entity_type",
                    "capability_signal",
                    "skills",
                    "internship_history",
                    "personality",
                    "soft_skills",
                    "trust_score",
                    "verification_status",
                ],
                [
                    sql_string(worker_id),
                    sql_string(worker.get("name") or worker_id),
                    sql_string(entity_type(worker_id, "ai_worker", "human_student")),
                    sql_number(worker.get("gpa")),
                    sql_number(worker.get("skills")),
                    sql_number(worker.get("internship")),
                    sql_number(worker.get("personality")),
                    sql_number(worker.get("soft")),
                    "0.80" if str(worker_id).startswith("AI") else "0.75",
                    sql_string("verified" if str(worker_id).startswith("AI") else "pending"),
                ],
            )
        )
        lines.append(
            insert(
                "worker_profiles",
                [
                    "worker_id",
                    "school_text",
                    "gpa_text",
                    "major_text",
                    "course_text",
                    "education_text",
                    "internship_text",
                    "skills_text",
                    "personality_text",
                    "soft_text",
                    "preference_text",
                ],
                [
                    sql_string(worker_id),
                    sql_string(profile.get("schoolText", "")),
                    sql_string(profile.get("gpaText", "")),
                    sql_string(profile.get("majorText", "")),
                    sql_string(profile.get("courseText", "")),
                    sql_string(profile.get("educationText", "")),
                    sql_string(profile.get("internshipText", "")),
                    sql_string(profile.get("skillsText", "")),
                    sql_string(profile.get("personalityText", "")),
                    sql_string(profile.get("softText", "")),
                    sql_string(profile.get("preferenceText", "")),
                ],
            )
        )
        lines.append(
            insert(
                "worker_preferences",
                ["worker_id", "salary_reward", "location_remote", "growth_opportunity", "reputation", "skill_fit_meaning"],
                [
                    sql_string(worker_id),
                    sql_number(weights.get("salary")),
                    sql_number(weights.get("location")),
                    sql_number(weights.get("career")),
                    sql_number(weights.get("reputation")),
                    sql_number(weights.get("meaning")),
                ],
            )
        )

    lines.append("")

    for employer in state["companies"]:
        employer_id = employer["id"]
        profile = state["companyProfiles"].get(employer_id, default_company_profile())
        weights = state["companyWeights"].get(employer_id, {})
        lines.append(
            insert(
                "employers",
                [
                    "id",
                    "name",
                    "entity_type",
                    "salary_reward",
                    "location_remote",
                    "growth_opportunity",
                    "reputation",
                    "skill_fit_meaning",
                    "trust_score",
                    "verification_status",
                ],
                [
                    sql_string(employer_id),
                    sql_string(employer.get("name") or employer_id),
                    sql_string(entity_type(employer_id, "ai_employer", "human_company")),
                    sql_number(employer.get("salary")),
                    sql_number(employer.get("location")),
                    sql_number(employer.get("career")),
                    sql_number(employer.get("reputation")),
                    sql_number(employer.get("meaning")),
                    "0.82" if str(employer_id).startswith("AI") else "0.76",
                    sql_string("verified" if str(employer_id).startswith("AI") else "pending"),
                ],
            )
        )
        lines.append(
            insert(
                "employer_profiles",
                ["employer_id", "salary_text", "location_text", "career_text", "reputation_text", "meaning_text", "candidate_text"],
                [
                    sql_string(employer_id),
                    sql_string(profile.get("salaryText", "")),
                    sql_string(profile.get("locationText", "")),
                    sql_string(profile.get("careerText", "")),
                    sql_string(profile.get("reputationText", "")),
                    sql_string(profile.get("meaningText", "")),
                    sql_string(profile.get("candidateText", "")),
                ],
            )
        )
        lines.append(
            insert(
                "employer_preferences",
                ["employer_id", "capability_signal", "skills", "internship_history", "personality", "soft_skills"],
                [
                    sql_string(employer_id),
                    sql_number(weights.get("gpa")),
                    sql_number(weights.get("skills")),
                    sql_number(weights.get("internship")),
                    sql_number(weights.get("personality")),
                    sql_number(weights.get("soft")),
                ],
            )
        )

    lines.append("")

    for worker in state["students"]:
        worker_id = worker["id"]
        for employer in state["companies"]:
            employer_id = employer["id"]
            lines.append(
                insert(
                    "utility_scores",
                    ["worker_id", "employer_id", "worker_to_employer_utility", "employer_to_worker_utility"],
                    [
                        sql_string(worker_id),
                        sql_string(employer_id),
                        sql_number(student_utilities[worker_id][employer_id]),
                        sql_number(company_utilities[employer_id][worker_id]),
                    ],
                )
            )

    for employer_id, worker_id in result["heldByCompany"].items():
        lines.append(
            insert(
                "matching_results",
                ["employer_id", "worker_id", "worker_utility", "employer_utility"],
                [
                    sql_string(employer_id),
                    sql_string(worker_id),
                    sql_number(student_utilities[worker_id][employer_id]),
                    sql_number(company_utilities[employer_id][worker_id]),
                ],
            )
        )

    for round_item in result["rounds"]:
        lines.append(
            insert(
                "algorithm_rounds",
                ["round_no", "payload"],
                [str(int(round_item["number"])), sql_string(json.dumps(round_item, ensure_ascii=False))],
            )
        )

    for worker in state["students"]:
        audit_probability, deposit, penalty = audit_values(worker["id"], "worker")
        lines.append(
            insert(
                "audit_records",
                ["entity_id", "entity_role", "audit_probability", "deposit_amount", "penalty_amount", "notes"],
                [
                    sql_string(worker["id"]),
                    sql_string("worker"),
                    sql_number(audit_probability),
                    sql_number(deposit),
                    sql_number(penalty),
                    sql_string("Generated by MySQL-only backend."),
                ],
            )
        )

    for employer in state["companies"]:
        audit_probability, deposit, penalty = audit_values(employer["id"], "employer")
        lines.append(
            insert(
                "audit_records",
                ["entity_id", "entity_role", "audit_probability", "deposit_amount", "penalty_amount", "notes"],
                [
                    sql_string(employer["id"]),
                    sql_string("employer"),
                    sql_number(audit_probability),
                    sql_number(deposit),
                    sql_number(penalty),
                    sql_string("Generated by MySQL-only backend."),
                ],
            )
        )

    return "\n".join(lines), result


def save_state(state: Dict[str, Any]) -> Dict[str, Any]:
    sql, result = build_save_sql(state)
    run_mysql(sql)
    return result


def reset_database() -> None:
    if not SEED_PATH.exists():
        raise FileNotFoundError("mysql_seed.sql not found")
    execute_sql_file(SEED_PATH, database=MYSQL_DATABASE)


def persist_computed_result(state: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Refresh utility/matching/round/audit tables after a read."""
    sql, _ = build_save_sql(state)
    run_mysql(sql)


def response_payload() -> Dict[str, Any]:
    state = apply_text_inference(load_state())
    result = compute_result(state)
    persist_computed_result(state, result)
    return {
        "state": state,
        "result": result,
        "database": f"mysql://{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}",
    }


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/state":
            self.write_json(response_payload())
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/state":
                body = self.read_json()
                save_state(body.get("state", {}))
                self.write_json(response_payload())
                return
            if path == "/api/reset":
                reset_database()
                self.write_json(response_payload())
                return
            self.write_json({"error": "Not found"}, status=404)
        except Exception as exc:  # noqa: BLE001 - user-facing API error payload
            self.write_json({"error": str(exc)}, status=500)

    def read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def write_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    os.chdir(BASE_DIR)
    ensure_database()
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Stable Hire MySQL-only server running at http://127.0.0.1:{PORT}/")
    print(f"Database: mysql://{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
    httpd.serve_forever()
