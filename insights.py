import json
import os
import re
import secrets
import shutil
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objs as go
import plotly.offline as pyo


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BATCH_DIR = os.path.join(DATA_DIR, "batches")
BATCH_INDEX = os.path.join(BATCH_DIR, "index.json")
RECIPES_FILE = os.path.join(DATA_DIR, "column_maps.json")
CARDS_FILE = os.path.join(DATA_DIR, "share_cards.json")

REQUIRED_FIELDS = [
    "Name",
    "USN",
    "Subject Name",
    "Subject Code",
    "Marks",
]

FIELD_ALIASES = {
    "Name": [
        "name",
        "student name",
        "student",
        "studentname",
        "stu name",
        "candidate",
        "candidate name",
    ],
    "USN": [
        "usn",
        "roll",
        "roll no",
        "rollno",
        "roll number",
        "reg no",
        "regno",
        "register number",
        "registration number",
        "university seat",
        "university seat number",
        "seat no",
        "seat number",
    ],
    "Subject Name": [
        "subject",
        "subject name",
        "paper",
        "paper name",
        "course",
        "course name",
        "sub name",
    ],
    "Subject Code": [
        "subject code",
        "code",
        "sub code",
        "course code",
        "paper code",
        "subcode",
    ],
    "Marks": [
        "marks",
        "mark",
        "score",
        "obtained",
        "obtained marks",
        "total marks",
        "cie",
        "see",
        "ia",
    ],
}


def _ensure_dirs():
    os.makedirs(BATCH_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(path, default):
    if not os.path.isfile(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path, payload):
    _ensure_dirs()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def normalize_header(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"[_\-./]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def guess_column_mapping(columns):
    unused = list(columns)
    mapping = {}

    exact = {normalize_header(column): column for column in columns}

    for field in REQUIRED_FIELDS:
        if field in columns:
            mapping[field] = field
            if field in unused:
                unused.remove(field)

    for field in REQUIRED_FIELDS:
        if field in mapping:
            continue

        for alias in FIELD_ALIASES.get(field, []):
            if alias in exact and exact[alias] in unused:
                mapping[field] = exact[alias]
                unused.remove(exact[alias])
                break

    return mapping, unused


def apply_column_mapping(df, mapping):
    rename = {
        source: field
        for field, source in mapping.items()
        if source and source in df.columns
    }
    mapped = df.rename(columns=rename)
    missing = [field for field in REQUIRED_FIELDS if field not in mapped.columns]

    if missing:
        raise ValueError("Missing mapped columns: " + ", ".join(missing))

    return mapped[REQUIRED_FIELDS].copy()


def load_recipes():
    data = _read_json(RECIPES_FILE, {"recipes": []})
    recipes = data.get("recipes") if isinstance(data, dict) else []
    return recipes if isinstance(recipes, list) else []


def save_recipe(name, source_columns, mapping):
    recipes = load_recipes()
    recipe = {
        "id": secrets.token_hex(8),
        "name": (name or "Saved mapping").strip() or "Saved mapping",
        "source_columns": list(source_columns),
        "mapping": mapping,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    recipes.insert(0, recipe)
    _write_json(RECIPES_FILE, {"recipes": recipes[:20]})
    return recipe


def matching_recipe(columns):
    source = set(str(column) for column in columns)

    for recipe in load_recipes():
        saved = set(recipe.get("source_columns") or [])
        if saved and saved == source:
            return recipe

    return None


def list_batches():
    data = _read_json(BATCH_INDEX, {"batches": []})
    batches = data.get("batches") if isinstance(data, dict) else []
    return batches if isinstance(batches, list) else []


def get_batch(batch_id):
    for batch in list_batches():
        if batch.get("id") == batch_id:
            return batch
    return None


def archive_batch(source_path, label, stats):
    _ensure_dirs()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_id = f"{stamp}_{secrets.token_hex(3)}"
    stored = os.path.join(BATCH_DIR, f"{batch_id}.xlsx")
    shutil.copy2(source_path, stored)

    batch = {
        "id": batch_id,
        "label": (label or "Dataset").strip() or "Dataset",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "path": stored,
        "stats": stats or {},
    }

    batches = list_batches()
    batches.insert(0, batch)
    _write_json(BATCH_INDEX, {"batches": batches[:30]})
    return batch


def batch_stats(student_df, subject_count):
    if student_df is None or student_df.empty:
        return {
            "students": 0,
            "pass_students": 0,
            "fail_students": 0,
            "pass_percentage": 0,
            "at_risk": 0,
            "subjects": int(subject_count or 0),
            "average": 0,
        }

    fail_students = int((student_df["Result"] == "FAIL").sum())
    total = len(student_df)
    pass_students = total - fail_students

    return {
        "students": total,
        "pass_students": pass_students,
        "fail_students": fail_students,
        "pass_percentage": round((pass_students / total) * 100, 2) if total else 0,
        "at_risk": fail_students,
        "subjects": int(subject_count or 0),
        "average": round(float(student_df["Percentage"].mean()), 2) if total else 0,
    }


def weakest_subjects(df, pass_mark):
    weakest = {}

    if df is None or df.empty:
        return weakest

    for usn, group in df.groupby("USN"):
        row = group.sort_values("Marks").iloc[0]
        weakest[usn] = {
            "subject": row["Subject Name"],
            "marks": float(row["Marks"]),
            "gap": round(max(0, pass_mark - float(row["Marks"])), 2),
        }

    return weakest


def counseling_queue(df, student_df, pass_mark):
    weakest = weakest_subjects(df, pass_mark)
    queue = []

    if student_df is None or student_df.empty:
        return queue

    at_risk = student_df[student_df["Failed Subjects"] >= 1].copy()

    for _, student in at_risk.iterrows():
        failed = int(student["Failed Subjects"])
        percentage = float(student["Percentage"])
        weak = weakest.get(student["USN"], {})
        subject = weak.get("subject") or "a failed subject"

        if failed >= 3 or percentage < 40:
            priority = "Critical"
            action = (
                f"HOD counseling this week. Build a recovery plan for {subject} "
                "and remaining backlogs before the next assessment."
            )
        elif failed >= 2 or percentage < 50:
            priority = "High"
            action = (
                f"Subject-teacher meeting plus remedial class for {subject}. "
                "Check attendance and internals."
            )
        else:
            priority = "Watch"
            action = (
                f"Assign a peer tutor for {subject} and review in 2 weeks. "
                "One more fail would put this student on the high-priority list."
            )

        queue.append(
            {
                "priority": priority,
                "rank_score": {"Critical": 0, "High": 1, "Watch": 2}[priority],
                "Name": student["Name"],
                "USN": student["USN"],
                "Failed Subjects": failed,
                "Percentage": student["Percentage"],
                "Weakest": subject,
                "Action": action,
            }
        )

    queue.sort(key=lambda item: (item["rank_score"], -item["Failed Subjects"], item["Percentage"]))
    return queue


def failure_chains(df, pass_mark, min_support=3):
    pairs = []

    if df is None or df.empty:
        return pairs, [], None

    pivot = df.pivot_table(
        index="USN",
        columns="Subject Name",
        values="Marks",
        aggfunc="max",
    )
    subjects = [str(name) for name in pivot.columns.tolist()]

    for source in subjects:
        for target in subjects:
            if source == target:
                continue

            both = pivot[[source, target]].dropna()
            if len(both) < min_support:
                continue

            failed_source = both[source] < pass_mark
            support = int(failed_source.sum())
            if support < min_support:
                continue

            conditional = float((both.loc[failed_source, target] < pass_mark).mean() * 100)
            baseline = float((both[target] < pass_mark).mean() * 100)
            lift = round(conditional - baseline, 1)

            pairs.append(
                {
                    "source": source,
                    "target": target,
                    "support": support,
                    "conditional": round(conditional, 1),
                    "baseline": round(baseline, 1),
                    "lift": lift,
                    "students": int(len(both)),
                }
            )

    pairs.sort(key=lambda item: (item["conditional"], item["lift"]), reverse=True)
    top_subjects = subjects[:12]
    chart = failure_chain_chart(pairs, top_subjects)
    return pairs[:20], top_subjects, chart


def failure_chain_chart(pairs, subjects):
    if not pairs or not subjects:
        return None

    lookup = {
        (item["source"], item["target"]): item["conditional"]
        for item in pairs
        if item["source"] in subjects and item["target"] in subjects
    }
    z_values = []

    for source in subjects:
        row = []
        for target in subjects:
            if source == target:
                row.append(None)
            else:
                row.append(lookup.get((source, target)))
        z_values.append(row)

    figure = go.Figure(
        go.Heatmap(
            z=z_values,
            x=subjects,
            y=subjects,
            colorscale=[
                [0, "#0f172a"],
                [0.35, "#1d4ed8"],
                [0.7, "#f59e0b"],
                [1, "#ef4444"],
            ],
            hovertemplate=(
                "Failed %{y}"
                "<br>then failed %{x}: %{z:.1f}%"
                "<extra></extra>"
            ),
            colorbar={"title": "%", "thickness": 12},
        )
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Segoe UI, Arial", "color": "#f8fafc", "size": 11},
        margin={"l": 90, "r": 24, "t": 36, "b": 90},
        height=420,
        title={
            "text": "If a student fails Y, how often do they also fail X?",
            "font": {"color": "#ffffff", "size": 14},
        },
        xaxis={"tickangle": -35, "automargin": True},
        yaxis={"automargin": True},
    )
    return pyo.plot(figure, output_type="div", include_plotlyjs=False)


def anomaly_flags(df, pass_mark):
    flags = []

    if df is None or df.empty:
        return flags

    for subject, group in df.groupby("Subject Name"):
        rounded = group["Marks"].round(0)
        counts = rounded.value_counts()
        size = len(group)
        threshold = max(4, int(size * 0.25))

        for mark, count in counts.items():
            if size < 8 or count < threshold:
                continue
            if mark in (0, 100):
                continue

            flags.append(
                {
                    "type": "Identical marks cluster",
                    "severity": "High" if count >= max(6, int(size * 0.4)) else "Watch",
                    "detail": (
                        f"{int(count)} students have exactly {int(mark)} in {subject} "
                        f"({round(count / size * 100, 1)}% of that paper)."
                    ),
                    "subject": subject,
                }
            )

    for usn, group in df.groupby("USN"):
        if len(group) < 3:
            continue

        name = group["Name"].iloc[0]

        for _, row in group.iterrows():
            others = group[group["Subject Name"] != row["Subject Name"]]["Marks"]
            if others.empty:
                continue

            other_avg = float(others.mean())
            mark = float(row["Marks"])

            if mark >= other_avg + 35 and other_avg < 55:
                flags.append(
                    {
                        "type": "Single-paper spike",
                        "severity": "Watch",
                        "detail": (
                            f"{name} ({usn}) scored {mark:.0f} in {row['Subject Name']} "
                            f"while averaging {other_avg:.1f} in other papers."
                        ),
                        "subject": row["Subject Name"],
                    }
                )

    name_groups = (
        df.groupby("Name")["USN"]
        .nunique()
        .sort_values(ascending=False)
    )

    for name, count in name_groups.items():
        if count < 2:
            continue

        usns = sorted(df.loc[df["Name"] == name, "USN"].unique().tolist())
        flags.append(
            {
                "type": "Same name, different USN",
                "severity": "Watch",
                "detail": (
                    f'"{name}" appears with {count} seat numbers: {", ".join(usns[:6])}'
                    + ("…" if count > 6 else "")
                    + ". Confirm these are different students."
                ),
                "subject": "Identity",
            }
        )

    severity_rank = {"High": 0, "Watch": 1}
    flags.sort(key=lambda item: severity_rank.get(item["severity"], 9))
    return flags[:40]


def backlog_planner(df, pass_mark):
    if df is None or df.empty:
        empty = pd.DataFrame(
            columns=["Name", "USN", "Subject Name", "Subject Code", "Marks", "Gap"]
        )
        return empty, pd.DataFrame(columns=["Subject", "Backlogs", "Average gap"])

    failed = df[df["Marks"] < pass_mark].copy()
    if failed.empty:
        empty = pd.DataFrame(
            columns=["Name", "USN", "Subject Name", "Subject Code", "Marks", "Gap"]
        )
        return empty, pd.DataFrame(columns=["Subject", "Backlogs", "Average gap"])

    failed["Gap"] = (pass_mark - failed["Marks"]).round(1)
    failed = failed.sort_values(["Subject Name", "Gap"], ascending=[True, False])

    summary = (
        failed.groupby("Subject Name", as_index=False)
        .agg(Backlogs=("USN", "count"), mean_gap=("Gap", "mean"))
        .sort_values("Backlogs", ascending=False)
    )
    summary["Average gap"] = summary["mean_gap"].round(1)
    summary = summary.rename(columns={"Subject Name": "Subject"})
    summary = summary[["Subject", "Backlogs", "Average gap"]]
    return failed, summary


def compare_student_sets(old_df, new_df):
    old_map = {
        row["USN"]: row
        for row in old_df.to_dict("records")
    } if old_df is not None and not old_df.empty else {}
    new_map = {
        row["USN"]: row
        for row in new_df.to_dict("records")
    } if new_df is not None and not new_df.empty else {}

    shared = sorted(set(old_map) & set(new_map))
    recovered = []
    slipped = []

    for usn in shared:
        previous = old_map[usn]
        current = new_map[usn]
        if previous.get("Result") == "FAIL" and current.get("Result") == "PASS":
            recovered.append(current)
        if previous.get("Result") == "PASS" and current.get("Result") == "FAIL":
            slipped.append(current)

    return {
        "shared": len(shared),
        "recovered": recovered[:25],
        "recovered_count": len(recovered),
        "slipped": slipped[:25],
        "slipped_count": len(slipped),
        "new_students": len(set(new_map) - set(old_map)),
        "missing_students": len(set(old_map) - set(new_map)),
    }


def load_share_cards():
    data = _read_json(CARDS_FILE, {"cards": {}})
    cards = data.get("cards") if isinstance(data, dict) else {}
    return cards if isinstance(cards, dict) else {}


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)

    return value


def save_share_card(payload):
    cards = load_share_cards()
    token = secrets.token_urlsafe(12)
    cards[token] = _json_safe(payload)
    _write_json(CARDS_FILE, {"cards": cards})
    return token


def get_share_card(token):
    return load_share_cards().get(token)


def qr_svg(url):
    try:
        import qrcode
        import qrcode.image.svg

        qr = qrcode.QRCode(border=1, box_size=8)
        qr.add_data(url)
        qr.make(fit=True)
        image = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
        return image.to_string(encoding="unicode")
    except Exception:
        return ""
