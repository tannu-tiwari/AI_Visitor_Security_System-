"""
One-time importer for the JSON/CSV visitor data.

Reads data/visitor_registrations.json, data/visitor_tracking.json and
data/visitor_logs.csv, copies them into a timestamped backup directory, then
imports every record into the SQLite database used by the application.

The source files are never modified or deleted. The script is idempotent:
running it again only inserts records that are not in the database yet.

Usage:
    python scripts/migrate_to_sqlite.py
    python scripts/migrate_to_sqlite.py --database data/visitor_management.db
    python scripts/migrate_to_sqlite.py --source-dir data --backup-dir backups/manual

The database path can also be set with the VISITOR_DB_PATH environment
variable (the application uses the same variable at startup).
"""

import argparse
import csv
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask  # noqa: E402

from core.database import db, init_database, resolve_database_path  # noqa: E402
from core.models import Approval, RecognitionEvent, Visit, Visitor  # noqa: E402

REGISTRATION_FILE = "visitor_registrations.json"
TRACKING_FILE = "visitor_tracking.json"
LOGS_FILE = "visitor_logs.csv"
SOURCE_FILES = (REGISTRATION_FILE, TRACKING_FILE, LOGS_FILE)


def parse_registration_time(value):
    value = str(value or "").strip()
    if not value:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_visit_time(date_value, time_value):
    date_value = str(date_value or "").strip()
    time_value = str(time_value or "").strip()

    if not date_value or not time_value:
        return None

    for date_fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        for time_fmt in ("%H:%M:%S", "%H:%M"):
            try:
                parsed_date = datetime.strptime(date_value, date_fmt)
                parsed_time = datetime.strptime(time_value, time_fmt)
                return parsed_date.replace(
                    hour=parsed_time.hour,
                    minute=parsed_time.minute,
                    second=parsed_time.second,
                )
            except ValueError:
                pass

    return None


def _new_counters():
    return {
        "migrated": 0,
        "skipped": 0,
        "failed": 0,
    }


def _read_json(path, report):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        report["errors"].append(f"{path.name}: could not read ({error})")
        return None

    if not isinstance(data, list):
        report["errors"].append(f"{path.name}: expected a JSON list")
        return None

    return data


def _find_visitor(name):
    visitor = db.session.execute(
        db.select(Visitor).where(Visitor.name == name).order_by(Visitor.id)
    ).scalars().first()
    if visitor is not None:
        return visitor

    return db.session.execute(
        db.select(Visitor)
        .where(db.func.lower(Visitor.name) == name.lower())
        .order_by(Visitor.id)
    ).scalars().first()


def migrate_registrations(records, report):
    counters = report["visitors"]

    for index, record in enumerate(records):
        label = f"{REGISTRATION_FILE}[{index}]"

        try:
            if not isinstance(record, dict):
                raise ValueError("record is not an object")

            registration_id = str(record.get("Registration ID") or "").strip()
            name = str(record.get("Name") or "").strip()

            if not registration_id or not name:
                raise ValueError("missing Registration ID or Name")

            existing = db.session.execute(
                db.select(Visitor).where(
                    Visitor.registration_id == registration_id
                )
            ).scalar_one_or_none()

            status = str(
                record.get("Approval Status") or "Pending"
            ).strip() or "Pending"

            if existing is not None:
                counters["skipped"] += 1
                if status in ("Approved", "Rejected"):
                    report["approvals"]["skipped"] += 1
                continue

            if status not in ("Pending", "Approved", "Rejected"):
                raise ValueError(f"invalid Approval Status {status!r}")

            registered_at = parse_registration_time(
                record.get("Registration Time")
            )
            if registered_at is None:
                raise ValueError("invalid Registration Time")

            visitor = Visitor(
                registration_id=registration_id,
                name=name,
                phone=str(record.get("Phone") or "").strip(),
                email=str(record.get("Email") or "").strip(),
                purpose=str(record.get("Purpose") or "").strip(),
                host=str(record.get("Host") or "").strip(),
                department=str(record.get("Department") or "").strip(),
                photo_filename=str(
                    record.get("Photo Filename") or ""
                ).strip(),
                registered_at=registered_at,
                approval_status=status,
            )

            db.session.add(visitor)
            db.session.flush()

            if status in ("Approved", "Rejected"):
                decided_at = None
                decision_at_value = str(
                    record.get("Decision At") or ""
                ).strip()
                if decision_at_value:
                    decided_at = parse_registration_time(
                        decision_at_value
                    )
                    if decided_at is None:
                        raise ValueError("invalid Decision At")

                db.session.add(Approval(
                    visitor_id=visitor.id,
                    decision=status,
                    decision_maker=(
                        str(record.get("Decision By") or "").strip()
                        or None
                    ),
                    decided_at=decided_at,
                    rejection_reason=(
                        str(record.get("Rejection Reason") or "").strip()
                        or None
                    ),
                ))

            db.session.commit()
            counters["migrated"] += 1

            if status in ("Approved", "Rejected"):
                report["approvals"]["migrated"] += 1

        except Exception as error:
            db.session.rollback()
            counters["failed"] += 1
            report["errors"].append(f"{label}: {error}")


def migrate_visits(records, report):
    counters = report["visits"]

    for index, record in enumerate(records):
        label = f"{TRACKING_FILE}[{index}]"

        try:
            if not isinstance(record, dict):
                raise ValueError("record is not an object")

            name = str(record.get("Visitor Name") or "").strip()
            entry_at = parse_visit_time(
                record.get("Entry Date"),
                record.get("Entry Time"),
            )

            if not name:
                raise ValueError("missing Visitor Name")
            if entry_at is None:
                raise ValueError("invalid Entry Date/Entry Time")

            exit_date = str(record.get("Exit Date") or "").strip()
            exit_time = str(record.get("Exit Time") or "").strip()
            exit_at = None

            if exit_date or exit_time:
                exit_at = parse_visit_time(exit_date, exit_time)
                if exit_at is None:
                    raise ValueError("invalid Exit Date/Exit Time")

            status = str(record.get("Status") or "").strip()
            if status not in ("Inside", "Exited"):
                status = "Exited" if exit_at is not None else "Inside"

            existing = db.session.execute(
                db.select(Visit).where(
                    Visit.visitor_name == name,
                    Visit.entry_at == entry_at,
                )
            ).scalar_one_or_none()

            if existing is not None:
                counters["skipped"] += 1
                continue

            visitor = _find_visitor(name)

            db.session.add(Visit(
                visitor_id=visitor.id if visitor is not None else None,
                visitor_name=name,
                entry_at=entry_at,
                exit_at=exit_at,
                status=status,
            ))
            db.session.commit()
            counters["migrated"] += 1

        except Exception as error:
            db.session.rollback()
            counters["failed"] += 1
            report["errors"].append(f"{label}: {error}")


def migrate_recognition_events(path, report):
    counters = report["recognition_events"]
    source_counts = Counter()

    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)

            for line_number, row in enumerate(reader, start=2):
                label = f"{LOGS_FILE}:{line_number}"

                try:
                    values = (
                        str(row.get("Visitor Name") or ""),
                        str(row.get("Date") or ""),
                        str(row.get("Time") or ""),
                        str(row.get("Status") or ""),
                    )
                    if not all(value.strip() for value in values):
                        raise ValueError("missing Visitor Name/Date/Time/Status")

                    source_counts[values] += 1

                except Exception as error:
                    counters["failed"] += 1
                    report["errors"].append(f"{label}: {error}")

    except OSError as error:
        report["errors"].append(f"{LOGS_FILE}: could not read ({error})")
        return

    existing_counts = Counter()

    if source_counts:
        events = db.session.execute(
            db.select(RecognitionEvent)
        ).scalars()

        for event in events:
            key = (
                event.visitor_name,
                event.event_date,
                event.event_time,
                event.status,
            )
            if key in source_counts:
                existing_counts[key] += 1

    for values, source_count in source_counts.items():
        missing = max(0, source_count - existing_counts[values])
        counters["skipped"] += source_count - missing

        if not missing:
            continue

        try:
            for _ in range(missing):
                db.session.add(RecognitionEvent(
                    visitor_name=values[0],
                    event_date=values[1],
                    event_time=values[2],
                    status=values[3],
                ))

            db.session.commit()
            counters["migrated"] += missing

        except Exception as error:
            db.session.rollback()
            counters["failed"] += missing
            report["errors"].append(
                f"{LOGS_FILE}: database write failed ({error})"
            )


def backup_sources(source_dir, backup_dir, database_path):
    backups = {}
    os.makedirs(backup_dir, exist_ok=True)

    for filename in SOURCE_FILES:
        source = os.path.join(source_dir, filename)
        if os.path.exists(source):
            target = os.path.join(backup_dir, filename)
            shutil.copy2(source, target)
            backups[source] = target

    if os.path.exists(database_path):
        target = os.path.join(
            backup_dir,
            os.path.basename(database_path) + ".before-migration"
        )
        shutil.copy2(database_path, target)
        backups[database_path] = target

    return backups


def migrate(source_dir, database_path, backup_dir=None, quiet=False):
    source_dir = os.path.abspath(source_dir)
    database_path = os.path.abspath(database_path)

    if backup_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(
            PROJECT_ROOT, "backups", f"migration_{timestamp}"
        )
    backup_dir = os.path.abspath(backup_dir)

    report = {
        "database": database_path,
        "source_dir": source_dir,
        "backup_dir": backup_dir,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "visitors": _new_counters(),
        "approvals": _new_counters(),
        "visits": _new_counters(),
        "recognition_events": _new_counters(),
        "errors": [],
        "backups": {},
    }

    report["backups"] = backup_sources(
        source_dir, backup_dir, database_path
    )

    app = Flask("visitor_migration")
    init_database(app, database_path)

    with app.app_context():
        registrations_path = os.path.join(source_dir, REGISTRATION_FILE)
        if os.path.exists(registrations_path):
            records = _read_json(registrations_path, report)
            if records is not None:
                migrate_registrations(records, report)

        tracking_path = os.path.join(source_dir, TRACKING_FILE)
        if os.path.exists(tracking_path):
            records = _read_json(tracking_path, report)
            if records is not None:
                migrate_visits(records, report)

        logs_path = os.path.join(source_dir, LOGS_FILE)
        if os.path.exists(logs_path):
            migrate_recognition_events(logs_path, report)

    report["finished_at"] = datetime.now().isoformat(timespec="seconds")

    report_path = os.path.join(backup_dir, "migration_report.json")
    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    if not quiet:
        print_report(report, report_path)

    return report


def print_report(report, report_path):
    print("Migrating visitor data to SQLite")
    print(f"  database:   {report['database']}")
    print(f"  sources:    {report['source_dir']}")
    print(f"  backups:    {report['backup_dir']}")

    for name in (
        "visitors",
        "approvals",
        "visits",
        "recognition_events",
    ):
        counters = report[name]
        print(
            f"  {name.replace('_', ' ').capitalize()}: "
            f"{counters['migrated']} migrated, "
            f"{counters['skipped']} skipped, "
            f"{counters['failed']} failed"
        )

    if report["errors"]:
        print(f"  Errors ({len(report['errors'])}):")
        for error in report["errors"][:20]:
            print(f"    - {error}")
        if len(report["errors"]) > 20:
            print(f"    ... and {len(report['errors']) - 20} more")

    print(f"  report:     {report_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Import legacy JSON/CSV visitor data into SQLite."
    )
    parser.add_argument(
        "--source-dir",
        default=os.path.join(PROJECT_ROOT, "data"),
        help="Directory containing the legacy JSON/CSV files.",
    )
    parser.add_argument(
        "--database",
        default=resolve_database_path(),
        help="SQLite database file to create or update.",
    )
    parser.add_argument(
        "--backup-dir",
        default=None,
        help="Directory for source-file backups (default: backups/migration_<time>).",
    )
    args = parser.parse_args(argv)

    report = migrate(
        args.source_dir,
        args.database,
        args.backup_dir,
    )

    has_failures = bool(report["errors"]) or any(
        report[name]["failed"]
        for name in ("visitors", "approvals", "visits", "recognition_events")
    )

    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
