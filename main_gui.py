import json
import math
import os
import secrets
import shutil
import sys
import subprocess
import tempfile
import tkinter as tk
import configparser
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

import supabase_client

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = APP_DIR


def prepare_installation() -> bool:
    if not getattr(sys, "frozen", False):
        return True

    source_executable = Path(sys.executable).resolve()
    install_dir = (
        source_executable.parent
        if source_executable.parent.name.casefold() == "jonasmatte"
        else source_executable.parent / "JonasMatte"
    )
    installed_executable = install_dir / source_executable.name
    template_dir = RESOURCE_DIR / "templates"

    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("config.ini", "README.md", "LISENS.txt"):
            target = install_dir / filename
            template = template_dir / filename
            if not target.exists():
                shutil.copyfile(template, target)

        if source_executable == installed_executable.resolve():
            return True

        shutil.copy2(source_executable, installed_executable)
        subprocess.Popen(
            [str(installed_executable)],
            cwd=str(install_dir),
            close_fds=True,
        )
        return False
    except OSError as error:
        tk_root = tk.Tk()
        tk_root.withdraw()
        messagebox.showerror(
            "Klargjøring av Jonas Matte",
            f"Kunne ikke opprette eller starte appen i:\n{install_dir}\n\n{error}",
            parent=tk_root,
        )
        tk_root.destroy()
        raise SystemExit(1) from error


if not prepare_installation():
    raise SystemExit(0)

USERS_FILE = APP_DIR / "users.jsonl"
NEWS_FILE = APP_DIR / "news.jsonl"
CONFIG_FILE = APP_DIR / "config.ini"
LOG_DIR = APP_DIR / "Logs"
LOG_FILE = LOG_DIR / "activity.jsonl"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3
APP_VERSION = "1"
uid: str | None = None
username: str | None = None
app_root: tk.Tk | None = None
current_session_id: str | None = None
logging_error_reported = False

def _rotate_activity_log() -> None:
    if not LOG_FILE.exists() or LOG_FILE.stat().st_size < LOG_MAX_BYTES:
        return

    oldest_backup = LOG_DIR / f"{LOG_FILE.stem}.{LOG_BACKUP_COUNT}.jsonl"
    if oldest_backup.exists():
        oldest_backup.unlink()
    for backup_number in range(LOG_BACKUP_COUNT - 1, 0, -1):
        old_backup = LOG_DIR / f"{LOG_FILE.stem}.{backup_number}.jsonl"
        if old_backup.exists():
            old_backup.replace(LOG_DIR / f"{LOG_FILE.stem}.{backup_number + 1}.jsonl")
    LOG_FILE.replace(LOG_DIR / f"{LOG_FILE.stem}.1.jsonl")

def log_event(
    event_name: str,
    details: dict[str, str | int | float | bool | None] | None = None,
) -> None:
    global logging_error_reported
    entry: dict[str, object] = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event_name,
        "app_version": APP_VERSION,
        "session_id": current_session_id,
    }
    if details:
        entry["details"] = details

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _rotate_activity_log()
        with LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as error:
        if not logging_error_reported:
            logging_error_reported = True
            if app_root is not None and app_root.winfo_exists():
                messagebox.showerror(
                    "Aktivitetslogg",
                    f"Kunne ikke skrive aktivitetsloggen: {error}",
                    parent=app_root,
                )

def start_session(method: str) -> None:
    global current_session_id
    current_session_id = uuid.uuid4().hex
    log_event("session.started", {"login_method": method})

def end_session(reason: str) -> None:
    global current_session_id
    if current_session_id is None:
        return
    log_event("session.ended", {"reason": reason})
    current_session_id = None

def _log_button_click(event: tk.Event) -> None:
    widget = event.widget
    try:
        if widget.winfo_class() not in {"Button", "TButton"}:
            return
        label = str(widget.cget("text")).strip()
    except tk.TclError:
        return
    if label:
        log_event("ui.button_clicked", {"button": label[:100]})

def schedule_background_task(
    parent: tk.Misc,
    delay_ms: int,
    task_name: str,
    callback: Callable[[], None],
) -> str:
    task_id = uuid.uuid4().hex
    log_event(
        "background.task_scheduled",
        {"task_id": task_id, "task": task_name, "delay_ms": delay_ms},
    )

    def run_task() -> None:
        log_event(
            "background.task_started",
            {"task_id": task_id, "task": task_name},
        )
        try:
            callback()
        except Exception as error:
            log_event(
                "background.task_failed",
                {"task_id": task_id, "task": task_name, "error_type": type(error).__name__},
            )
            raise
        log_event(
            "background.task_completed",
            {"task_id": task_id, "task": task_name},
        )

    return parent.after(delay_ms, run_task)

def load_app_config() -> tuple[bool, str]:
    config = configparser.ConfigParser()
    try:
        if CONFIG_FILE.exists():
            with CONFIG_FILE.open("r", encoding="utf-8") as file:
                config.read_file(file)
        auto_login_jonas = config.getboolean(
            "app",
            "auto_login_jonas",
            fallback=False,
        )
        jonas_user_id = config.get(
            "app",
            "jonas_user_id",
            fallback="426030",
        ).strip()
    except (OSError, configparser.Error, ValueError) as error:
        raise ValueError(f"Kunne ikke lese {CONFIG_FILE.name}: {error}") from error

    if not jonas_user_id and auto_login_jonas:
        raise ValueError(f"Verdien jonas_user_id i {CONFIG_FILE.name} kan ikke være tom.")
    if not jonas_user_id:
        jonas_user_id = "426030"
    return auto_login_jonas, jonas_user_id

def remember_jonas_session(parent: tk.Misc, user_id: str) -> None:
    if not AUTO_LOGIN_JONAS or user_id != JONAS_USER_ID:
        return
    try:
        supabase_client.remember_session(user_id)
    except supabase_client.SupabaseError as error:
        log_event("auth.auto_login_session_save_failed")
        messagebox.showwarning(
            "Automatisk innlogging",
            f"Innloggingen fungerte, men økten kunne ikke lagres for automatisk innlogging: {error}",
            parent=parent,
        )

def generate_login_token(parent: tk.Misc) -> None:
    if supabase_client.is_enabled():
        messagebox.showerror(
            "Innloggingstoken",
            "Innloggingstoken støttes ikke for Supabase-kontoer ennå.",
            parent=parent,
        )
        return
    if uid is None:
        messagebox.showerror(
            "Innloggingstoken",
            "Du må være logget inn for å opprette et innloggingstoken.",
            parent=parent,
        )
        return

    users = read_users(parent)
    if users is None:
        return

    user = next((entry for entry in users if entry.get("user_id") == uid), None)
    if user is None:
        messagebox.showerror(
            "Innloggingstoken",
            "Fant ikke den innloggede brukeren i users.jsonl.",
            parent=parent,
        )
        return

    token = secrets.token_urlsafe(32)
    user["token"] = token
    if not save_users(users, parent):
        return

    token_window = tk.Toplevel(parent)
    token_window.title("Innloggingstoken")
    token_window.geometry("460x220")
    token_window.resizable(False, False)
    token_window.transient(parent)

    content = ttk.Frame(token_window, padding=24)
    content.pack(fill="both", expand=True)
    ttk.Label(
        content,
        text="Det nye innloggingstokenet ditt:",
        font=("Arial", 12, "bold"),
    ).pack(pady=(0, 8))

    token_entry = ttk.Entry(content, width=52)
    token_entry.insert(0, token)
    token_entry.configure(state="readonly")
    token_entry.pack(fill="x", pady=(0, 10))

    ttk.Label(
        content,
        text="Det forrige innloggingstokenet er nå ugyldig.",
    ).pack(pady=(0, 12))

    copy_button = ttk.Button(content, text="Kopier token")
    copy_button.pack()

    def copy_token() -> None:
        try:
            token_window.clipboard_clear()
            token_window.clipboard_append(token)
            token_window.update()
        except tk.TclError as error:
            messagebox.showerror(
                "Innloggingstoken",
                f"Kunne ikke kopiere tokenet: {error}",
                parent=token_window,
            )
            return
        copy_button.configure(text="Kopiert!")

    copy_button.configure(command=copy_token)
    token_window.lift()

def login_tk_page(run_mainloop: bool = True) -> None:
    global app_root, uid, username
    if app_root is None:
        app_root = tk.Tk()
        app_root.withdraw()
        app_root.bind_all("<ButtonPress-1>", _log_button_click, add="+")
        log_event("app.started", {"auto_login_jonas": AUTO_LOGIN_JONAS})
        log_event(
            "config.loaded",
            {"setting": "auto_login_jonas", "value": AUTO_LOGIN_JONAS},
        )
    login_page = open_window(app_root)
    login_page.geometry("400x600")
    login_page.title("Logg inn eller registrer deg")

    welcome_msg = tk.Label(login_page, text="Jonas Matte", font=("Arial", 18))
    welcome_msg.pack(pady=20)

    subtitle_msg = tk.Label(login_page, text="Logg inn eller registrer deg", font=("Arial", 10))
    subtitle_msg.pack(pady=1)

    login_button = ttk.Button(
        login_page,
        text="Logg inn",
        width=20,
        padding=(12, 8),
        command=lambda: login(login_page),
    )
    login_button.pack(pady=10)

    register_button = ttk.Button(
        login_page,
        text="Registrer deg",
        width=20,
        padding=(12, 8),
        command=lambda: register(login_page),
    )
    register_button.pack(pady=10)

    token_button = ttk.Button(
        login_page,
        text="Logg inn med token",
        width=20,
        padding=(12, 8),
        command=lambda: insert_token(login_page),
    )
    token_button.pack(pady=10)

    if AUTO_LOGIN_JONAS and supabase_client.is_enabled():
        try:
            jonas = supabase_client.restore_session(JONAS_USER_ID)
        except supabase_client.SupabaseError as error:
            log_event("auth.auto_login_failed", {"reason": "supabase_session"})
            messagebox.showerror(
                "Automatisk innlogging",
                f"Kunne ikke gjenopprette Supabase-økten: {error}\n"
                "Logg inn med brukernavn og passord.",
                parent=login_page,
            )
        else:
            if jonas is not None:
                saved_username = jonas.get("username")
                if not isinstance(saved_username, str):
                    supabase_client.clear_session()
                    messagebox.showerror(
                        "Automatisk innlogging",
                        "Jonas-kontoen mangler et gyldig brukernavn.",
                        parent=login_page,
                    )
                else:
                    uid = JONAS_USER_ID
                    username = saved_username
                    start_session("automatic")
                    main(login_page)
            else:
                messagebox.showinfo(
                    "Automatisk innlogging",
                    "Logg inn med Jonas-kontoen én gang med brukernavn og passord. "
                    "Deretter kan appen logge inn automatisk.",
                    parent=login_page,
                )
    elif AUTO_LOGIN_JONAS:
        users = read_users(login_page)
        if users is None:
            close_window(login_page)
            return
        jonas = next(
            (user for user in users if user.get("user_id") == JONAS_USER_ID),
            None,
        )
        if jonas is None:
            messagebox.showerror(
                "Automatisk innlogging",
                f"Fant ikke Jonas med bruker-ID {JONAS_USER_ID}.",
                parent=login_page,
            )
            close_window(login_page)
            return

        saved_username = jonas.get("username")
        if not isinstance(saved_username, str):
            messagebox.showerror(
                "Automatisk innlogging",
                "Jonas-kontoen mangler et gyldig brukernavn.",
                parent=login_page,
            )
            close_window(login_page)
            return

        uid = JONAS_USER_ID
        username = saved_username
        start_session("automatic")
        main(login_page)

    if run_mainloop:
        app_root.mainloop()

def stop() -> None:

    global app_root, uid, username

    end_session("application_exit")
    log_event("app.stopped")
    uid = None
    username = None

    if app_root is not None and app_root.winfo_exists():
        app_root.destroy() 

def open_window(parent: tk.Misc) -> tk.Toplevel:
    if app_root is None:
        raise RuntimeError("Tkinter-vinduet er ikke startet.")

    window = tk.Toplevel(app_root)
    window.protocol("WM_DELETE_WINDOW", lambda: close_window(window))
    if parent is not app_root:
        try:
            if parent.winfo_exists():
                parent.destroy()
        except tk.TclError:
            pass
    return window

def play_same_sequence(parent: tk.Misc) -> None:
    if uid is None:
        messagebox.showerror(
            "Sekvens",
            "Ingen bruker er logget inn.",
            parent=parent,
        )
        return

    users = read_users(parent)
    if users is None:
        return
    user = next((entry for entry in users if entry.get("user_id") == uid), None)
    if user is None:
        messagebox.showerror(
            "Statistikk",
            "Fant ikke den innloggede brukeren i users.jsonl.",
            parent=parent,
        )
        return

    last_sequence = user.get("last_sequence")
    if not isinstance(last_sequence, list) or not all(
        isinstance(item, str) for item in last_sequence
    ):
        messagebox.showerror(
            "Sekvens",
            "Fant ingen gyldig sekvens for den innloggede brukeren.",
            parent=parent,
        )
        return
    if not last_sequence:
        messagebox.showinfo(
            "Ingen lagret sekvens",
            "Skriv inn en sekvens eller spill et tilfeldig spill for å lagre en.",
            parent=parent,
        )
        return

    sequence: list[str] = []
    for equation in last_sequence:
        factors = equation.split("*")
        if len(factors) != 2 or not all(
            factor.strip().isdigit() and int(factor.strip()) > 0
            for factor in factors
        ):
            messagebox.showerror(
                "Ugyldig sekvens",
                f"Sekvensen «{equation}» i users.jsonl er ugyldig.",
                parent=parent,
            )
            return
        sequence.append(
            f"{int(factors[0].strip())}*{int(factors[1].strip())}"
        )

    log_event(
        "game.started",
        {"game_type": "saved_sequence", "question_count": len(sequence)},
    )
    correct = 0
    wrong = 0

    preview_window = open_window(parent)
    preview_window.title("Spill lagret sekvens")
    preview_window.geometry("560x400")

    preview = ttk.Frame(preview_window, padding=30)
    preview.pack(fill="both", expand=True)
    ttk.Label(
        preview,
        text="Jonas Matte",
        font=("Arial", 24, "bold"),
    ).pack(pady=(0, 6))
    ttk.Label(
        preview,
        text=f"Brukernavn: {username}",
        font=("Arial", 11),
        justify="center",
    ).pack(pady=(0, 20))

    ttk.Label(
        preview,
        text="Spill lagret sekvens",
        font=("Arial", 18, "bold"),
    ).pack(pady=(0, 25))

    def show_round(round_index: int, previous_window: tk.Misc) -> None:
        nonlocal correct, wrong
        round_window = open_window(previous_window)
        round_number = round_index + 1
        first_factor, second_factor = map(int, sequence[round_index].split("*"))
        round_window.title(f"Runde {round_number} av {len(sequence)}")
        round_window.geometry("520x380")
        round_window.minsize(400, 300)

        content = ttk.Frame(round_window, padding=32)
        content.pack(fill="both", expand=True)
        ttk.Label(
            content,
            text="Spill lagret sekvens",
            font=("Arial", 18, "bold"),
        ).pack(pady=(0, 16))
        ttk.Label(
            content,
            text=f"Runde {round_number} av {len(sequence)}",
            font=("Arial", 22, "bold"),
        ).pack(pady=(0, 8))
        ttk.Progressbar(
            content,
            maximum=len(sequence),
            value=round_number,
        ).pack(fill="x", pady=(0, 20))
        ttk.Label(
            content,
            text=f"Hva er {first_factor} × {second_factor}?",
            font=("Arial", 24),
        ).pack(pady=(0, 12))

        answer = tk.StringVar()
        answer_entry = ttk.Entry(
            content,
            textvariable=answer,
            justify="center",
            font=("Arial", 16),
        )
        answer_entry.pack(pady=(0, 10))
        feedback = ttk.Label(content, text="", font=("Arial", 12))
        feedback.pack(pady=(0, 14))

        def continue_game() -> None:
            if round_number < len(sequence):
                show_round(round_index + 1, round_window)
                return

            log_event(
                "game.completed",
                {
                    "game_type": "saved_sequence",
                    "correct_answers": correct,
                    "wrong_answers": wrong,
                    "question_count": len(sequence),
                },
            )
            saved_stats = record_game_results(
                round_window,
                correct,
                wrong,
                sequence,
            )
            finished_window = open_window(round_window)
            finished_window.title("Ferdig")
            finished_window.geometry("520x520")
            finished_window.minsize(420, 460)
            summary = ttk.Frame(finished_window, padding=28)
            summary.pack(fill="both", expand=True)
            ttk.Label(
                summary,
                text="Ferdig!",
                font=("Arial", 25, "bold"),
            ).pack(pady=(0, 12))
            ttk.Label(
                summary,
                text=(
                    f"Resultat for denne sekvensen ({len(sequence)} spørsmål):\n"
                    f"Riktige svar: {correct}\n"
                    f"Feil svar: {wrong}\n"
                    f"Poeng denne runden: {correct - wrong * 0.5:+g}"
                ),
                font=("Arial", 13),
                justify="center",
            ).pack(pady=(0, 16))

            if saved_stats is not None:
                total_questions = saved_stats["total-questions"]
                accuracy = (
                    saved_stats["correct-answers"] / total_questions * 100
                    if total_questions
                    else 0
                )
                ttk.Label(
                    summary,
                    text=(
                        "Samlet statistikk:\n"
                        f"Poeng: {saved_stats['points']:g}\n"
                        f"Riktige svar: {saved_stats['correct-answers']:g}\n"
                        f"Feil svar: {saved_stats['wrong-answers']:g}\n"
                        f"Totalt antall spørsmål: {total_questions:g}\n"
                        f"Treffsikkerhet: {accuracy:.1f}%"
                    ),
                    font=("Arial", 12),
                    justify="center",
                ).pack(pady=(0, 16))
            else:
                ttk.Label(
                    summary,
                    text="Resultatet kunne ikke lagres i users.jsonl.",
                    font=("Arial", 11),
                    justify="center",
                ).pack(pady=(0, 16))

            ttk.Button(
                summary,
                text="Spill lagret sekvens igjen",
                command=lambda: play_same_sequence(finished_window),
            ).pack(pady=5)
            ttk.Button(
                summary,
                text="Tilbake til hovedmenyen",
                command=lambda: main(finished_window),
            ).pack(pady=5)

        def submit_answer() -> None:
            nonlocal correct, wrong
            try:
                submitted_answer = int(answer.get().strip())
            except ValueError:
                log_event(
                    "game.answer_rejected",
                    {"game_type": "saved_sequence", "round": round_number},
                )
                messagebox.showerror(
                    "Ugyldig svar",
                    "Skriv inn et heltall.",
                    parent=round_window,
                )
                answer_entry.focus_set()
                return

            if submitted_answer == first_factor * second_factor:
                feedback.configure(text="Riktig!")
                correct += 1
                answer_correct = True
            else:
                feedback.configure(
                    text=f"Ikke helt. Riktig svar er {first_factor * second_factor}."
                )
                wrong += 1
                answer_correct = False
            log_event(
                "game.answer_submitted",
                {
                    "game_type": "saved_sequence",
                    "round": round_number,
                    "correct": answer_correct,
                },
            )
            answer_entry.configure(state="disabled")
            answer_button.configure(state="disabled")
            schedule_background_task(
                round_window,
                1000,
                "continue_saved_sequence_game",
                continue_game,
            )

        answer_button = ttk.Button(
            content,
            text="Svar",
            padding=(18, 10),
            command=submit_answer,
        )
        answer_button.pack()
        answer_entry.bind("<Return>", lambda _event: submit_answer())
        answer_entry.focus_set()

        round_window.update_idletasks()
        x = (round_window.winfo_screenwidth() - round_window.winfo_width()) // 2
        y = (round_window.winfo_screenheight() - round_window.winfo_height()) // 2
        round_window.geometry(f"+{x}+{y}")

    ttk.Button(
        preview,
        text="Start spill",
        padding=(18, 10),
        command=lambda: show_round(0, preview_window),
    ).pack(pady=(0, 8))
    ttk.Button(
        preview,
        text="Tilbake til hovedmenyen",
        command=lambda: main(preview_window),
    ).pack()

def enter_sequence(parent: tk.Misc) -> None:
    sequence_window = open_window(parent)
    sequence_window.title("Skriv inn sekvens")
    sequence_window.geometry("400x300")

    ttk.Label(
        sequence_window,
        text="Skriv inn en sekvens med multiplikasjonsoppgaver.",
        font=("Arial", 14),
    ).pack(pady=10)
    ttk.Label(
        sequence_window,
        text="Eksempel: 2*3, 4*5, 6*7",
        font=("Arial", 10),
    ).pack(pady=5)

    sequence_var = tk.StringVar()
    sequence_entry = ttk.Entry(sequence_window, textvariable=sequence_var, width=40)
    sequence_entry.pack(pady=10)

    def submit_sequence() -> None:
        sequence_input = sequence_var.get().strip()
        if not sequence_input:
            messagebox.showerror(
                "Ugyldig sekvens",
                "Skriv inn en gyldig sekvens.",
                parent=sequence_window,
            )
            return

        sequence_list: list[str] = []
        for item in sequence_input.split(","):
            factors = [factor.strip() for factor in item.split("*")]
            if len(factors) != 2:
                messagebox.showerror(
                    "Ugyldig sekvens",
                    f"Ugyldig format i «{item.strip()}». Bruk formatet «a*b».",
                    parent=sequence_window,
                )
                return
            if not all(factor.isdigit() for factor in factors):
                messagebox.showerror(
                    "Ugyldig sekvens",
                    f"«{item.strip()}» må inneholde to positive heltall.",
                    parent=sequence_window,
                )
                return
            try:
                first_factor, second_factor = map(int, factors)
            except ValueError:
                messagebox.showerror(
                    "Ugyldig sekvens",
                    "Tallene i sekvensen er for store.",
                    parent=sequence_window,
                )
                return
            if first_factor <= 0 or second_factor <= 0:
                messagebox.showerror(
                    "Ugyldig sekvens",
                    f"«{item.strip()}» må inneholde to positive heltall.",
                    parent=sequence_window,
                )
                return
            sequence_list.append(f"{first_factor}*{second_factor}")

        if uid is None:
            messagebox.showerror(
                "Ugyldig innlogging",
                "Du må være logget inn for å lagre en sekvens.",
                parent=sequence_window,
            )
            return
        users = read_users(sequence_window)
        if users is None:
            return
        user = next((entry for entry in users if entry.get("user_id") == uid), None)
        if user is None:
            messagebox.showerror(
                "Brukerdatabase",
                "Fant ikke den innloggede brukeren i users.jsonl.",
                parent=sequence_window,
            )
            return
        user["last_sequence"] = sequence_list
        if not save_users(users, sequence_window):
            return
        log_event(
            "game.sequence_saved",
            {"question_count": len(sequence_list)},
        )
        play_same_sequence(sequence_window)

    ttk.Button(sequence_window, text="Send inn", command=submit_sequence).pack(pady=10)
    sequence_entry.focus_set()

    ttk.Button(
            sequence_window,
            text="Tilbake til hovedmenyen",
            command=lambda: main(sequence_window),
        ).pack(pady=25)

def close_window(window: tk.Toplevel) -> None:
    window.destroy()
    if app_root is not None and app_root.winfo_exists() and not app_root.winfo_children():
        end_session("window_closed")
        log_event("app.stopped")
        app_root.destroy()

def log_out(window: tk.Misc) -> None:
    global uid, username
    temp_username = username
    log_event("auth.logged_out")
    end_session("logout")
    if supabase_client.has_session():
        try:
            supabase_client.forget_saved_session()
        except supabase_client.SupabaseError as error:
            messagebox.showerror(
                "Automatisk innlogging",
                f"Kunne ikke fjerne den lagrede Supabase-økten: {error}",
                parent=window,
            )
    supabase_client.clear_session()
    uid = None
    username = None 
    messagebox.showinfo(
        "Logg ut",
        f"Du er logget ut fra brukeren {temp_username}.",
        parent=window,
    )

    window.destroy()
    login_tk_page(run_mainloop=False)

def change_password(parent: tk.Misc) -> None:
    if uid is None:
        messagebox.showerror(
            "Endre passord",
            "Ingen bruker er logget inn.",
            parent=parent,
        )
        return

    users = read_users(parent)
    if users is None:
        return
    user = next((entry for entry in users if entry.get("user_id") == uid), None)
    if user is None:
        messagebox.showerror(
            "Endre passord",
            "Fant ikke den innloggede brukeren i users.jsonl.",
            parent=parent,
        )
        return

    change_window = open_window(parent)
    change_window.title("Endre passord")
    change_window.geometry("400x250")

    ttk.Label(change_window, text="Endre passord", font=("Arial", 14)).pack(pady=10)
    ttk.Label(change_window, text="Skriv inn et nytt passord:", font=("Arial", 10)).pack(pady=5)

    new_password_var = tk.StringVar()
    new_password_entry = ttk.Entry(change_window, textvariable=new_password_var, width=30, show="*")
    new_password_entry.pack(pady=10)

    def submit_new_password() -> None:
        new_password = new_password_var.get().strip()
        if not new_password:
            messagebox.showerror(
                "Ugyldig passord",
                "Vennligst skriv inn et gyldig passord.",
                parent=change_window,
            )
            return

        if supabase_client.is_enabled():
            try:
                supabase_client.change_password(new_password)
            except supabase_client.SupabaseError as error:
                messagebox.showerror(
                    "Endre passord",
                    f"Kunne ikke endre passordet i Supabase: {error}",
                    parent=change_window,
                )
                return
        else:
            user["password"] = new_password
            if not save_users(users, change_window):
                return

        log_event("settings.updated", {"setting": "password"})
        messagebox.showinfo(
            "Passord endret",
            "Passordet ditt er nå endret.",
            parent=change_window,
        )
        settings_and_news(change_window)

    ttk.Button(
        change_window,
        text="Endre passord",
        command=submit_new_password,
    ).pack(pady=10)
    new_password_entry.focus_set()

    ttk.Button(
        change_window,
        text="Tilbake til innstillinger/nyheter",
        command=lambda: settings_and_news(change_window),
    ).pack(pady=10)

def news(parent: tk.Misc) -> None:
    show_updates(parent, "news")

def version_log(parent: tk.Misc) -> None:
    show_updates(parent, "version")

def show_updates(parent: tk.Misc, item_type: str) -> None:
    if item_type not in {"news", "version"}:
        raise ValueError("Ugyldig type oppdatering.")
    is_version_log = item_type == "version"
    page_title = "Versjonslogg" if is_version_log else "Nyheter"
    entry_label = "versjonslogginnlegg" if is_version_log else "nyhetsinnlegg"
    news_parent = parent
    if uid is None:
        messagebox.showerror(
            page_title,
            "Ingen bruker er logget inn.",
            parent=news_parent,
        )
        return
    users = read_users(news_parent)
    if users is None:
        return
    current_user = next(
        (user for user in users if user.get("user_id") == uid),
        None,
    )
    if current_user is None:
        messagebox.showerror(
            page_title,
            "Fant ikke den innloggede brukeren i users.jsonl.",
            parent=news_parent,
        )
        return
    is_admin = current_user.get("admin") is True

    news_items: list[dict[str, object]] = []
    all_news_items: list[dict[str, object]] = []
    if supabase_client.is_enabled():
        try:
            news_items = [
                dict(item)
                for item in supabase_client.read_news(item_type)
            ]
        except supabase_client.SupabaseError as error:
            log_event(
                "storage.read_failed",
                {
                    "backend": "supabase",
                    "resource": "news_items",
                    "item_type": item_type,
                    "operation": "read",
                },
            )
            messagebox.showerror(
                page_title,
                f"Kunne ikke lese innleggene fra Supabase: {error}",
                parent=news_parent,
            )
            return
        log_event(
            "storage.read_completed",
            {
                "backend": "supabase",
                "resource": "news_items",
                "item_type": item_type,
                "operation": "read",
                "record_count": len(news_items),
            },
        )
    else:
        log_event(
            "storage.read_started",
            {"backend": "local_jsonl", "resource": NEWS_FILE.name, "operation": "read"},
        )
        try:
            with NEWS_FILE.open("r", encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if not isinstance(item, dict) or not all(
                        isinstance(item.get(field), str)
                        for field in ("title", "body", "author", "created_at")
                    ):
                        raise ValueError(
                            f"Linje {line_number} i news.jsonl har ugyldig format."
                        )
                    stored_type = item.get("item_type", "news")
                    if not isinstance(stored_type, str) or stored_type not in {
                        "news",
                        "version",
                    }:
                        raise ValueError(
                            f"Linje {line_number} i news.jsonl har ugyldig innleggstype."
                        )
                    item["_local_index"] = len(all_news_items)
                    all_news_items.append(item)
                    if stored_type == item_type:
                        news_items.append(item)
        except FileNotFoundError:
            log_event(
                "storage.read_completed",
                {
                    "backend": "local_jsonl",
                    "resource": NEWS_FILE.name,
                    "operation": "read",
                    "record_count": 0,
                    "file_exists": False,
                },
            )
        except (OSError, json.JSONDecodeError, ValueError) as error:
            log_event(
                "storage.read_failed",
                {
                    "backend": "local_jsonl",
                    "resource": NEWS_FILE.name,
                    "operation": "read",
                    "error_type": type(error).__name__,
                },
            )
            messagebox.showerror(
                page_title,
                f"Kunne ikke lese nyhetsfilen: {error}",
                parent=news_parent,
            )
            return
        else:
            log_event(
                "storage.read_completed",
                {
                    "backend": "local_jsonl",
                    "resource": NEWS_FILE.name,
                    "operation": "read",
                    "record_count": len(news_items),
                    "file_exists": True,
                },
            )

    news_window = open_window(parent)
    news_window.title(page_title)
    news_window.geometry("600x590")

    content = ttk.Frame(news_window, padding=16)
    content.pack(fill="both", expand=True)
    ttk.Label(
        content,
        text="Versjonslogg" if is_version_log else "Nyheter og oppdateringer",
        font=("Arial", 16, "bold"),
    ).pack(pady=(0, 12))

    updates_frame = ttk.Frame(content)
    updates_frame.pack(fill="both", expand=True)
    scrollbar = ttk.Scrollbar(updates_frame)
    scrollbar.pack(side="right", fill="y")
    updates_canvas = tk.Canvas(
        updates_frame,
        yscrollcommand=scrollbar.set,
        highlightthickness=0,
    )
    updates_canvas.pack(side="left", fill="both", expand=True)
    scrollbar.configure(command=updates_canvas.yview)
    updates_list = ttk.Frame(updates_canvas)
    updates_window_id = updates_canvas.create_window(
        (0, 0),
        window=updates_list,
        anchor="nw",
    )
    updates_list.bind(
        "<Configure>",
        lambda _event: updates_canvas.configure(
            scrollregion=updates_canvas.bbox("all")
        ),
    )
    updates_canvas.bind(
        "<Configure>",
        lambda event: updates_canvas.itemconfigure(
            updates_window_id,
            width=event.width,
        ),
    )

    if news_items:
        for item in reversed(news_items):
            post = ttk.Frame(updates_list, padding=(8, 8))
            post.pack(fill="x", expand=True, pady=(0, 8))
            ttk.Label(
                post,
                text=str(item["title"]),
                font=("Arial", 12, "bold"),
                wraplength=510,
                justify="left",
            ).pack(anchor="w")
            ttk.Label(
                post,
                text=f"{item['created_at']} — {item['author']}",
                font=("Arial", 9),
                wraplength=510,
                justify="left",
            ).pack(anchor="w", pady=(2, 6))
            ttk.Label(
                post,
                text=str(item["body"]),
                wraplength=510,
                justify="left",
            ).pack(anchor="w", fill="x")

            if is_admin:
                def delete_item(selected_item: dict[str, object] = item) -> None:
                    if not messagebox.askyesno(
                        f"Slett {entry_label}",
                        f"Er du sikker på at du vil slette «{selected_item['title']}»?",
                        parent=news_window,
                    ):
                        return

                    if supabase_client.is_enabled():
                        item_id = selected_item.get("id")
                        if not isinstance(item_id, str):
                            messagebox.showerror(
                                page_title,
                                "Innlegget mangler en gyldig Supabase-ID.",
                                parent=news_window,
                            )
                            return
                        try:
                            supabase_client.delete_news(item_id)
                        except supabase_client.SupabaseError as error:
                            log_event(
                                "storage.delete_failed",
                                {
                                    "backend": "supabase",
                                    "resource": "news_items",
                                    "item_type": item_type,
                                },
                            )
                            messagebox.showerror(
                                page_title,
                                f"Kunne ikke slette innlegget fra Supabase: {error}",
                                parent=news_window,
                            )
                            return
                        log_event(
                            "storage.delete_completed",
                            {
                                "backend": "supabase",
                                "resource": "news_items",
                                "item_type": item_type,
                            },
                        )
                    else:
                        selected_index = selected_item.get("_local_index")
                        if not isinstance(selected_index, int):
                            messagebox.showerror(
                                page_title,
                                "Innlegget mangler en gyldig lokal ID.",
                                parent=news_window,
                            )
                            return
                        remaining_items = [
                            stored_item
                            for index, stored_item in enumerate(all_news_items)
                            if index != selected_index
                        ]
                        temporary_path: str | None = None
                        log_event(
                            "storage.write_started",
                            {
                                "backend": "local_jsonl",
                                "resource": NEWS_FILE.name,
                                "operation": "delete",
                            },
                        )
                        try:
                            with tempfile.NamedTemporaryFile(
                                mode="w",
                                encoding="utf-8",
                                dir=NEWS_FILE.parent,
                                delete=False,
                            ) as file:
                                temporary_path = file.name
                                for stored_item in remaining_items:
                                    saved_item = {
                                        key: value
                                        for key, value in stored_item.items()
                                        if key != "_local_index"
                                    }
                                    file.write(
                                        json.dumps(saved_item, ensure_ascii=False) + "\n"
                                    )
                            os.replace(temporary_path, NEWS_FILE)
                        except OSError as error:
                            if temporary_path is not None:
                                try:
                                    os.unlink(temporary_path)
                                except OSError:
                                    pass
                            log_event(
                                "storage.write_failed",
                                {
                                    "backend": "local_jsonl",
                                    "resource": NEWS_FILE.name,
                                    "operation": "delete",
                                    "error_type": type(error).__name__,
                                },
                            )
                            messagebox.showerror(
                                page_title,
                                f"Kunne ikke slette innlegget: {error}",
                                parent=news_window,
                            )
                            return
                        log_event(
                            "storage.write_completed",
                            {
                                "backend": "local_jsonl",
                                "resource": NEWS_FILE.name,
                                "operation": "delete",
                            },
                        )
                    log_event("news.deleted", {"item_type": item_type})
                    show_updates(news_window, item_type)

                ttk.Button(
                    post,
                    text="Slett innlegg",
                    command=delete_item,
                ).pack(anchor="e", pady=(8, 0))
            ttk.Separator(updates_list, orient="horizontal").pack(
                fill="x",
                pady=(0, 8),
            )
    else:
        empty_text = (
            "Det er ingen versjonslogginnlegg ennå."
            if is_version_log
            else "Det er ingen nyheter ennå."
        )
        ttk.Label(updates_list, text=empty_text).pack(anchor="w", padx=8, pady=8)

    if is_admin:
        def create_update() -> None:
            editor = open_window(news_window)
            editor.title(
                "Skriv versjonslogginnlegg" if is_version_log else "Skriv nyhetsoppdatering"
            )
            editor.geometry("500x430")

            form = ttk.Frame(editor, padding=16)
            form.pack(fill="both", expand=True)
            ttk.Label(form, text="Overskrift:").pack(anchor="w")
            title_entry = ttk.Entry(form)
            title_entry.pack(fill="x", pady=(0, 12))
            ttk.Label(
                form,
                text="Versjonslogginnlegg:" if is_version_log else "Nyhet:",
            ).pack(anchor="w")
            body_text = tk.Text(form, height=12, wrap="word")
            body_text.pack(fill="both", expand=True, pady=(0, 12))

            def publish() -> None:
                title = title_entry.get().strip()
                body = body_text.get("1.0", "end").strip()
                if not title or not body:
                    messagebox.showerror(
                        page_title,
                        f"Skriv inn både overskrift og tekst for {entry_label}.",
                        parent=editor,
                    )
                    return

                news_item = {
                    "title": title,
                    "body": body,
                    "author": username or "Administrator",
                    "item_type": item_type,
                    "created_at": datetime.now().astimezone().isoformat(
                        timespec="minutes"
                    ),
                }
                if supabase_client.is_enabled():
                    try:
                        supabase_client.publish_news(news_item)
                    except supabase_client.SupabaseError as error:
                        log_event(
                            "storage.write_failed",
                            {
                                "backend": "supabase",
                                "resource": "news_items",
                                "item_type": item_type,
                            },
                        )
                        messagebox.showerror(
                            page_title,
                            f"Kunne ikke publisere innlegget i Supabase: {error}",
                            parent=editor,
                        )
                        return
                    log_event(
                        "storage.write_completed",
                        {
                            "backend": "supabase",
                            "resource": "news_items",
                            "item_type": item_type,
                        },
                    )
                    log_event("news.published", {"item_type": item_type})
                    show_updates(editor, item_type)
                    return

                log_event(
                    "storage.write_started",
                    {
                        "backend": "local_jsonl",
                        "resource": NEWS_FILE.name,
                        "operation": "append",
                        "item_type": item_type,
                    },
                )
                try:
                    with NEWS_FILE.open("a", encoding="utf-8") as file:
                        file.write(
                            json.dumps(news_item, ensure_ascii=False) + "\n"
                        )
                except OSError as error:
                    log_event(
                        "storage.write_failed",
                        {
                            "backend": "local_jsonl",
                            "resource": NEWS_FILE.name,
                            "operation": "append",
                            "item_type": item_type,
                            "error_type": type(error).__name__,
                        },
                    )
                    messagebox.showerror(
                        page_title,
                        f"Kunne ikke lagre innlegget: {error}",
                        parent=editor,
                    )
                    return

                log_event(
                    "storage.write_completed",
                    {
                        "backend": "local_jsonl",
                        "resource": NEWS_FILE.name,
                        "operation": "append",
                        "item_type": item_type,
                    },
                )
                log_event("news.published", {"item_type": item_type})
                show_updates(editor, item_type)

            ttk.Button(
                form,
                text="Publiser versjonslogg" if is_version_log else "Publiser nyhet",
                command=publish,
            ).pack()

        ttk.Button(
            content,
            text="Lag versjonslogginnlegg" if is_version_log else "Lag nyhetsoppdatering",
            command=create_update,
        ).pack(pady=(12, 0))

    ttk.Button(
        content,
        text="Tilbake til innstillinger/nyheter",
        command=lambda: settings_and_news(news_window),
    ).pack(pady=(12, 0))

def change_username(parent: tk.Misc) -> None:
    change_window = open_window(parent)
    change_window.title("Endre brukernavn")
    change_window.geometry("400x250")

    ttk.Label(change_window, text="Endre brukernavn", font=("Arial", 14)).pack(pady=10)
    ttk.Label(change_window, text="Skriv inn et nytt brukernavn:", font=("Arial", 10)).pack(pady=5)

    new_username_var = tk.StringVar()
    new_username_entry = ttk.Entry(change_window, textvariable=new_username_var, width=30)
    new_username_entry.pack(pady=10)

    def submit_new_username() -> None:
        new_username = new_username_var.get().strip()
        if not new_username:
            messagebox.showerror(
                "Ugyldig brukernavn",
                "Vennligst skriv inn et gyldig brukernavn.",
                parent=change_window,
            )
            return

        users = read_users(change_window)
        if users is None:
            return
        for entry in users:
            saved_username = entry.get("username")
            if (
                entry.get("user_id") != uid
                and isinstance(saved_username, str)
                and saved_username.casefold() == new_username.casefold()
            ):
                messagebox.showerror(
                    "Brukernavn",
                    "Brukernavnet er allerede tatt.",
                    parent=change_window,
                )
                return
        user = next((entry for entry in users if entry.get("user_id") == uid), None)
        if user is None:
            messagebox.showerror(
                "Brukernavn",
                "Fant ikke den innloggede brukeren i users.jsonl.",
                parent=change_window,
            )
            return

        user["username"] = new_username
        if not save_users(users, change_window):
            return

        global username
        username = new_username
        log_event("settings.updated", {"setting": "username"})
        messagebox.showinfo(
            "Brukernavn endret",
            f"Brukernavnet ditt er nå endret til {new_username}.",
            parent=change_window,
        )
        settings_and_news(change_window)

    ttk.Button(change_window, text="Endre brukernavn", command=submit_new_username).pack(pady=10)
    new_username_entry.focus_set()

    ttk.Button(
        change_window,
        text="Tilbake til innstillinger/nyheter",
        command=lambda: settings_and_news(change_window),
    ).pack(pady=(12, 0))

def delete_user(parent: tk.Misc) -> None:
    global uid, username
    if uid is None:
        messagebox.showerror(
            "Slett bruker",
            "Ingen bruker er logget inn.",
            parent=parent,
        )
        return

    confirm = messagebox.askyesno(
        "Slett bruker",
        "Er du sikker på at du vil slette brukeren din? Dette kan ikke angres.",
        parent=parent,
    )
    if not confirm:
        return

    if supabase_client.is_enabled():
        try:
            supabase_client.delete_account()
        except supabase_client.SupabaseError as error:
            messagebox.showerror(
                "Slett bruker",
                f"Kunne ikke slette kontoen fra Supabase: {error}",
                parent=parent,
            )
            return
    else:
        users = read_users(parent)
        if users is None:
            return
        user_index = next(
            (i for i, entry in enumerate(users) if entry.get("user_id") == uid),
            None,
        )
        if user_index is None:
            messagebox.showerror(
                "Slett bruker",
                "Fant ikke den innloggede brukeren i users.jsonl.",
                parent=parent,
            )
            return

        del users[user_index]
        if not save_users(users, parent):
            return

    log_event("account.deleted")
    end_session("account_deleted")
    uid = None
    username = None
    messagebox.showinfo(
        "Bruker slettet",
        "Brukeren din er nå slettet.",
        parent=parent,
    )

    parent.destroy()
    login_tk_page(run_mainloop=False)

def credits_and_attributions(parent: tk.Misc) -> None:
    credits_window = open_window(parent)
    credits_window.title("Lisens og attribusjoner")
    credits_window.geometry("750x400")

    ttk.Label(
        credits_window,
        text="Lisens og attribusjoner",
        font=("Arial", 23)
    ).pack(pady=20)

    text_frame = ttk.Frame(credits_window)
    text_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    scrollbar = ttk.Scrollbar(text_frame, orient="vertical")
    credits_text = tk.Text(
        text_frame,
        wrap="word",
        yscrollcommand=scrollbar.set,
        padx=10,
        pady=10,
    )
    scrollbar.configure(command=credits_text.yview)
    credits_text.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    credits_text.insert(
        "1.0",
        "MIT-lisensen (originalteksten er på engelsk)\n\n"
        "Copyright 2026 Jonas\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\n"
        "THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n\n"
        "Kreditering\n\n"
        "Utviklet av Jonas, med hjelp fra KI-verktøy i Visual Studio Code.\n\n"
        "Programmet er åpen kildekode og lisensiert under MIT-lisensen.",
    )
    credits_text.configure(state="disabled")

def settings_and_news(parent: tk.Misc) -> None:
    settings_window = open_window(parent)
    settings_window.title("Innstillinger og nyheter")
    settings_window.geometry("400x800")

    ttk.Label(settings_window, text="Innstillinger og nyheter", font=("Arial", 14)).pack(pady=10)
    ttk.Label(
        settings_window,
        text="Her kan du endre innstillinger og se nyheter/oppdateringer om programmet.",
        font=("Arial", 10),
        wraplength=360,
        justify="center",
    ).pack(pady=5)
    ttk.Label(settings_window, text=f"Brukernavn: {username}", font=("Arial", 8)).pack(pady=5)

    danger_button_style = ttk.Style(settings_window)
    danger_button_style.configure("Danger.TButton", foreground="red")
    danger_button_style.map(
        "Danger.TButton",
        foreground=[("disabled", "gray"), ("!disabled", "red")],
    )

    ttk.Button(
        settings_window,
        text="Nyheter",
        command=lambda: news(settings_window),
        width=20,
    ).pack(pady=10, ipadx=10, ipady=6)

    ttk.Button(
        settings_window,
        text="Versjonslogg",
        command=lambda: version_log(settings_window),
        width=20,
    ).pack(pady=0, ipadx=10, ipady=6)

    ttk.Button(
            settings_window,
            text="Endre brukernavn",
            command=lambda: change_username(settings_window),
            width=20,
        ).pack(pady=10, ipadx=10, ipady=6)

    ttk.Button(
        settings_window,
        text="Endre passord",
        command=lambda: change_password(settings_window),
        width=20,
    ).pack(pady=10, ipadx=10, ipady=6)

    ttk.Button(
        settings_window,
        text="Slett bruker",
        command=lambda: delete_user(settings_window),
        width=20,
        style="Danger.TButton",
    ).pack(pady=10, ipadx=10, ipady=6)

    ttk.Button(
        settings_window,
        text="Tilbake til hovedmenyen",
        command=lambda: main(settings_window),
    ).pack(pady=20)

    ttk.Label(
        settings_window,
        text=f"Versjon {APP_VERSION}",
        font=("Arial", 8),
    ).pack(side="bottom", pady=8)

def main(window: tk.Misc) -> None:
    window = open_window(window)
    window.title("Jonas Matte")
    window.geometry("400x800")

    # Bakgrunnsbildet brukes bare på hovedmenyen.
    try:
        window.background_image = tk.PhotoImage(
            master=window,
            file=str(
                (APP_DIR / "bg.png")
                if (APP_DIR / "bg.png").is_file()
                else (RESOURCE_DIR / "bg.png")
            ),
        )
    except tk.TclError as error:
        messagebox.showerror(
            "Bakgrunnsbilde",
            f"Kunne ikke laste bg.png: {error}",
            parent=window,
        )
    else:
        background = tk.Label(window, image=window.background_image, borderwidth=0)
        background.place(x=0, y=0, relwidth=1, relheight=1)

    # Standard Tk/ttk-widgets for menyinnholdet.
    ttk.Label(window, text="Jonas Matte").pack(pady=5)
    ttk.Label(window, text=f"Brukernavn: {username}").pack(pady=10)

    def add_menu_button(text: str, command: Callable[[], None]) -> None:
        tk.Button(
            window,
            text=text,
            width=20,
            background="#999999",
            activebackground="#858585",
            command=command,
        ).pack(pady=10)

    add_menu_button(
        "Nytt tilfeldig spill",
        lambda: random_game(window),
    )
    add_menu_button(
        "Se statistikk",
        lambda: show_stats(window),
    )
    add_menu_button(
        "Skriv inn sekvens",
        lambda: enter_sequence(window),
    )

    add_menu_button(
        "Spill lagret sekvens",
        lambda: play_same_sequence(window),
    )

    ttk.Separator(window, orient="horizontal").pack(fill="x", pady=10)

    add_menu_button(
        "Generer innloggingstoken",
        lambda: generate_login_token(window),
    )
    add_menu_button(
        "Logg ut",
        lambda: log_out(window),
    )

    ttk.Separator(window, orient="horizontal").pack(fill="x", pady=10)

    add_menu_button(
        "Innstillinger og nyheter",
        lambda: settings_and_news(window),
    )
    add_menu_button(
            "Lisens og attribusjoner",
            lambda: credits_and_attributions(window),
        )
    add_menu_button(
        "Avslutt",
        lambda: stop(),
    )
    
    ttk.Label(
        window,
        font=("Arial", 8),
        text="Versjon " + APP_VERSION,
    ).pack(pady=10)

def save_users(users: list[dict[str, object]], parent: tk.Misc) -> bool:
    if supabase_client.is_enabled():
        user = next((entry for entry in users if entry.get("user_id") == uid), None)
        if user is None:
            messagebox.showerror(
                "Brukerdatabase",
                "Fant ikke den innloggede brukeren i Supabase.",
                parent=parent,
            )
            return False
        try:
            supabase_client.update_profile(user)
        except supabase_client.SupabaseError as error:
            log_event(
                "storage.write_failed",
                {"backend": "supabase", "resource": "user_profiles"},
            )
            messagebox.showerror(
                "Brukerdatabase",
                f"Kunne ikke lagre brukerdata i Supabase: {error}",
                parent=parent,
            )
            return False
        log_event(
            "storage.write_completed",
            {"backend": "supabase", "resource": "user_profiles"},
        )
        return True

    temporary_path: str | None = None
    log_event(
        "storage.write_started",
        {"backend": "local_jsonl", "resource": USERS_FILE.name, "operation": "replace"},
    )
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=USERS_FILE.parent,
            prefix=f".{USERS_FILE.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = file.name
            for user in users:
                file.write(json.dumps(user, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, USERS_FILE)
    except OSError as error:
        log_event(
            "storage.write_failed",
            {
                "backend": "local_jsonl",
                "resource": USERS_FILE.name,
                "operation": "replace",
                "error_type": type(error).__name__,
            },
        )
        messagebox.showerror(
            "Brukerdatabase",
            f"Kunne ikke lagre brukerdata: {error}",
            parent=parent,
        )
        return False
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            try:
                os.unlink(temporary_path)
            except OSError as error:
                messagebox.showerror(
                    "Brukerdatabase",
                    f"Kunne ikke rydde opp etter lagring: {error}",
                    parent=parent,
                )
    log_event(
        "storage.write_completed",
        {"backend": "local_jsonl", "resource": USERS_FILE.name, "operation": "replace"},
    )
    return True

def show_stats(parent: tk.Misc) -> None:
    users = read_users(parent)
    if users is None:
        return
    user = next((entry for entry in users if entry.get("user_id") == uid), None)
    if user is None:
        messagebox.showerror(
            "Statistikk",
            "Fant ikke den innloggede brukeren i users.jsonl.",
            parent=parent,
        )
        return

    stats = user.get("stats")
    if stats is None:
        stats = {}
    if not isinstance(stats, dict):
        messagebox.showerror(
            "Statistikk",
            "Statistikken i users.jsonl har ugyldig format.",
            parent=parent,
        )
        return

    values: dict[str, int | float] = {}
    defaults = {
        "points": 0,
        "correct-answers": 0,
        "wrong-answers": 0,
        "total-questions": 0,
    }
    for field, default in defaults.items():
        value = stats.get(field, default)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            messagebox.showerror(
                "Statistikk",
                f"Verdien for «{field}» i users.jsonl er ugyldig.",
                parent=parent,
            )
            return
        values[field] = value

    total_questions = values["total-questions"]
    accuracy = (
        values["correct-answers"] / total_questions * 100
        if total_questions
        else 0
    )
    stats_window = open_window(parent)
    stats_window.title("Statistikk")
    stats_window.geometry("420x360")

    content = ttk.Frame(stats_window, padding=28)
    content.pack(fill="both", expand=True)
    ttk.Label(content, text="Samlet statistikk", font=("Arial", 22, "bold")).pack(
        pady=(0, 20)
    )

    ttk.Label(content, text=f"Brukernavn: {username}", font=("Arial", 12, "bold")).pack(
            pady=(0, 10)
        )
    
    ttk.Label(
        content,
        text=(
            f"Poeng: {values['points']:g}\n"
            f"Riktige svar: {values['correct-answers']:g}\n"
            f"Feil svar: {values['wrong-answers']:g}\n"
            f"Totalt antall spørsmål: {total_questions:g}\n"
            f"Treffsikkerhet: {accuracy:.1f}%"
        ),
        font=("Arial", 14),
        justify="center",
    ).pack(pady=(0, 20))
    ttk.Button(
        content,
        text="Tilbake",
        command=lambda: main(stats_window),
    ).pack()

def record_game_results(
    parent: tk.Misc,
    correct: int,
    wrong: int,
    sequence: list[str],
) -> dict[str, int | float] | None:
    if uid is None:
        messagebox.showerror(
            "Statistikk",
            "Ingen bruker er logget inn.",
            parent=parent,
        )
        return None

    users = read_users(parent)
    if users is None:
        return None
    user = next((entry for entry in users if entry.get("user_id") == uid), None)
    if user is None:
        messagebox.showerror(
            "Statistikk",
            "Fant ikke den innloggede brukeren i users.jsonl.",
            parent=parent,
        )
        return None

    stats = user.get("stats")
    if stats is None:
        stats = {}
        user["stats"] = stats
    if not isinstance(stats, dict):
        messagebox.showerror(
            "Statistikk",
            "Statistikken i users.jsonl har ugyldig format.",
            parent=parent,
        )
        return None

    values: dict[str, int | float] = {}
    defaults = {
        "points": 0,
        "correct-answers": 0,
        "wrong-answers": 0,
        "total-questions": 0,
    }
    for field, default in defaults.items():
        value = stats.get(field, default)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            messagebox.showerror(
                "Statistikk",
                f"Verdien for «{field}» i users.jsonl er ugyldig.",
                parent=parent,
            )
            return None
        values[field] = value

    values["points"] += correct - wrong * 0.5
    values["correct-answers"] += correct
    values["wrong-answers"] += wrong
    values["total-questions"] += correct + wrong
    stats.update(values)
    user["last_sequence"] = sequence
    if not save_users(users, parent):
        return None
    return values

def random_game(parent: tk.Misc) -> None:
    random_game_window = open_window(parent)
    random_game_window.title("Nytt tilfeldig spill")
    random_game_window.geometry("450x600")

    ttk.Label(random_game_window, text="Nytt tilfeldig spill", font=("Arial", 18)).pack(pady=5)
    ttk.Label(random_game_window, text=f"Brukernavn: {username}").pack(pady=10)

    ttk.Label(random_game_window, text="Gangetabell").pack(anchor="w")
    ttk.Label(
        random_game_window,
        text="Velg en tabell, eller velg «Alle» for blandede oppgaver.",
    ).pack(anchor="w", pady=(0, 6))
    table = tk.StringVar(value="0: Alle")
    table_choices = ["0: Alle"] + [
        f"{number}: {number}-gangen" for number in range(1, 11)
    ]
    table_combobox = ttk.Combobox(
        random_game_window,
        textvariable=table,
        values=table_choices,
        state="readonly",
    )
    table_combobox.pack(fill="x", padx=20, pady=8)

    def open_selected_table(_event: tk.Event | None = None) -> None:
        selected_table = int(table.get().split(":", 1)[0])
        for widget in random_game_window.winfo_children():
            widget.destroy()

        ttk.Label(random_game_window, text="Nytt tilfeldig spill", font=("Arial", 18)).pack(pady=5)
        ttk.Label(random_game_window, text=f"Brukernavn: {username}").pack(pady=10)

        rounds = tk.StringVar()

        ttk.Label(random_game_window, text="Antall runder:").pack()
        rounds_entry = ttk.Entry(
            random_game_window,
            textvariable=rounds,
        )
        rounds_entry.pack()

        def actual_random_game(_event: tk.Event | None = None) -> None:
            rounds_value = rounds.get().strip()
            if not rounds_value.isdigit() or int(rounds_value) <= 0:
                messagebox.showerror(
                    "Ugyldig antall runder",
                    "Vennligst skriv inn et positivt heltall for antall runder.",
                    parent=random_game_window,
                )
                return
            rounds_int = int(rounds_value)
            log_event(
                "game.started",
                {
                    "game_type": "random",
                    "question_count": rounds_int,
                    "multiplication_table": selected_table,
                },
            )
            correct = 0
            wrong = 0
            sequence: list[str] = []

            def show_round(round_index: int, previous_window: tk.Misc) -> None:
                round_window = open_window(previous_window)
                round_number = round_index + 1
                rounds_remaining = rounds_int - round_number
                round_window.title(f"Runde {round_number} av {rounds_int}")
                round_window.geometry("520x380")
                round_window.minsize(400, 300)

                first_factor = (
                    secrets.randbelow(10) + 1
                    if selected_table == 0
                    else selected_table
                )
                second_factor = secrets.randbelow(10) + 1
                sequence.append(f"{first_factor}*{second_factor}")

                content = ttk.Frame(round_window, padding=32)
                content.pack(fill="both", expand=True)

                ttk.Label(
                    content,
                    text="Nytt tilfeldig spill",
                    font=("Arial", 18, "bold"),
                ).pack(pady=(0, 16))
                ttk.Label(
                    content,
                    text=f"Runde {round_number} av {rounds_int}",
                    font=("Arial", 22, "bold"),
                ).pack(pady=(0, 8))
                ttk.Progressbar(
                    content,
                    maximum=rounds_int,
                    value=round_number,
                ).pack(fill="x", pady=(0, 20))
                ttk.Label(
                    content,
                    text=f"Hva er {first_factor} × {second_factor}?",
                    font=("Arial", 24),
                ).pack(pady=(0, 12))

                answer = tk.StringVar()
                answer_entry = ttk.Entry(
                    content,
                    textvariable=answer,
                    justify="center",
                    font=("Arial", 16),
                )
                answer_entry.pack(pady=(0, 10))
                feedback = ttk.Label(content, text="", font=("Arial", 12))
                feedback.pack(pady=(0, 14))

                def continue_game() -> None:
                    if rounds_remaining:
                        show_round(round_index + 1, round_window)
                    else:
                        log_event(
                            "game.completed",
                            {
                                "game_type": "random",
                                "correct_answers": correct,
                                "wrong_answers": wrong,
                                "question_count": rounds_int,
                            },
                        )
                        saved_stats = record_game_results(
                            round_window,
                            correct,
                            wrong,
                            sequence,
                        )
                        finished_window = open_window(round_window)
                        finished_window.title("Ferdig")
                        finished_window.geometry("520x520")
                        finished_window.minsize(420, 460)

                        content = ttk.Frame(finished_window, padding=28)
                        content.pack(fill="both", expand=True)
                        ttk.Label(
                            content,
                            text="Ferdig!",
                            font=("Arial", 25, "bold"),
                        ).pack(pady=(0, 10))
                        ttk.Label(
                            content,
                            text=f"Resultat for dette spillet ({rounds_int} spørsmål)",
                            font=("Arial", 14),
                        ).pack(pady=(0, 10))
                        ttk.Label(
                            content,
                            text=(
                                f"Riktige svar: {correct}\n"
                                f"Feil svar: {wrong}\n"
                                f"Poeng denne runden: {correct - wrong * 0.5:+g}"
                            ),
                            font=("Arial", 13),
                            justify="center",
                        ).pack(pady=(0, 16))

                        if saved_stats is not None:
                            total_questions = saved_stats["total-questions"]
                            accuracy = (
                                saved_stats["correct-answers"] / total_questions * 100
                                if total_questions
                                else 0
                            )
                            ttk.Label(
                                content,
                                text=(
                                    "Samlet statistikk:\n"
                                    f"Poeng: {saved_stats['points']:g}\n"
                                    f"Riktige svar: {saved_stats['correct-answers']:g}\n"
                                    f"Feil svar: {saved_stats['wrong-answers']:g}\n"
                                    f"Totalt antall spørsmål: {total_questions:g}\n"
                                    f"Treffsikkerhet: {accuracy:.1f}%"
                                ),
                                font=("Arial", 12),
                                justify="center",
                            ).pack(pady=(0, 16))
                        else:
                            ttk.Label(
                                content,
                                text="Spillresultatet kunne ikke lagres i users.jsonl.",
                                font=("Arial", 11),
                                justify="center",
                            ).pack(pady=(0, 16))

                        ttk.Button(
                            content,
                            text="Spill på nytt",
                            command=lambda: random_game(finished_window),
                        ).pack(pady=5)
                        ttk.Button(
                            content,
                            text="Tilbake til hovedmenyen",
                            command=lambda: main(finished_window),
                        ).pack(pady=5)

                def submit_answer() -> None:
                    nonlocal correct, wrong
                    try:
                        submitted_answer = int(answer.get().strip())
                    except ValueError:
                        log_event(
                            "game.answer_rejected",
                            {"game_type": "random", "round": round_number},
                        )
                        messagebox.showerror(
                            "Ugyldig svar",
                            "Skriv inn et heltall.",
                            parent=round_window,
                        )
                        answer_entry.focus_set()
                        return

                    if submitted_answer == first_factor * second_factor:
                        feedback.configure(text="Riktig!")
                        correct += 1
                        answer_correct = True
                    else:
                        feedback.configure(
                            text=f"Ikke helt. Riktig svar er {first_factor * second_factor}."
                        )
                        wrong += 1
                        answer_correct = False
                    log_event(
                        "game.answer_submitted",
                        {
                            "game_type": "random",
                            "round": round_number,
                            "correct": answer_correct,
                        },
                    )

                    answer_entry.configure(state="disabled")
                    answer_button.configure(state="disabled")
                    schedule_background_task(
                        round_window,
                        1000,
                        "continue_random_game",
                        continue_game,
                    )

                answer_button = ttk.Button(
                    content,
                    text="Svar",
                    padding=(18, 10),
                    command=submit_answer,
                )
                answer_button.pack()
                answer_entry.bind("<Return>", lambda _event: submit_answer())
                answer_entry.focus_set()

                round_window.update_idletasks()
                x = (round_window.winfo_screenwidth() - round_window.winfo_width()) // 2
                y = (round_window.winfo_screenheight() - round_window.winfo_height()) // 2
                round_window.geometry(f"+{x}+{y}")

            show_round(0, random_game_window)

        rounds_entry.bind("<Return>", actual_random_game)
        ttk.Button(
            random_game_window,
            text="Start spill",
            command=actual_random_game,
        ).pack(pady=10)
        rounds_entry.focus_set()
    

    table_combobox.bind("<Return>", open_selected_table)
    ttk.Button(
        random_game_window,
        text="Fortsett",
        command=open_selected_table,
    ).pack(pady=12)
    table_combobox.focus_set()

    ttk.Button(
        random_game_window,
        text="Tilbake til hovedmenyen",
        command=lambda: main(random_game_window),
    ).pack(pady=20)

def read_users(parent: tk.Misc) -> list[dict[str, object]] | None:
    if supabase_client.is_enabled():
        if not supabase_client.has_session():
            return []
        try:
            user = supabase_client.get_profile()
        except supabase_client.SupabaseError as error:
            log_event(
                "storage.read_failed",
                {"backend": "supabase", "resource": "user_profiles"},
            )
            messagebox.showerror(
                "Brukerdatabase",
                f"Kunne ikke lese brukerprofilen fra Supabase: {error}",
                parent=parent,
            )
            return None
        if user is None:
            return []
        log_event(
            "storage.read_completed",
            {
                "backend": "supabase",
                "resource": "user_profiles",
                "record_count": 1,
            },
        )
        return [user]

    users: list[dict[str, object]] = []
    log_event(
        "storage.read_started",
        {"backend": "local_jsonl", "resource": USERS_FILE.name, "operation": "read"},
    )
    try:
        with USERS_FILE.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                user = json.loads(line)
                if not isinstance(user, dict):
                    raise ValueError(f"Linje {line_number} må inneholde et objekt.")
                users.append(user)
    except FileNotFoundError:
        log_event(
            "storage.read_completed",
            {
                "backend": "local_jsonl",
                "resource": USERS_FILE.name,
                "operation": "read",
                "record_count": 0,
                "file_exists": False,
            },
        )
        return users
    except OSError as error:
        log_event(
            "storage.read_failed",
            {
                "backend": "local_jsonl",
                "resource": USERS_FILE.name,
                "operation": "read",
                "error_type": type(error).__name__,
            },
        )
        messagebox.showerror(
            "Brukerdatabase",
            f"Kunne ikke åpne users.jsonl: {error}",
            parent=parent,
        )
        return None
    except (json.JSONDecodeError, ValueError) as error:
        log_event(
            "storage.read_failed",
            {
                "backend": "local_jsonl",
                "resource": USERS_FILE.name,
                "operation": "read",
                "error_type": type(error).__name__,
            },
        )
        messagebox.showerror(
            "Brukerdatabase",
            f"Brukerdatabasen har feil: {error}",
            parent=parent,
        )
        return None
    log_event(
        "storage.read_completed",
        {
            "backend": "local_jsonl",
            "resource": USERS_FILE.name,
            "operation": "read",
            "record_count": len(users),
            "file_exists": True,
        },
    )
    return users

def login(parent: tk.Misc) -> None:
    login_window = open_window(parent)
    login_window.title("Logg inn")
    login_window.geometry("320x230")
    login_window.resizable(False, False)

    tk.Label(login_window, text="Brukernavn:").pack(pady=(18, 4))
    username_entry = ttk.Entry(login_window, width=30)
    username_entry.pack()

    tk.Label(login_window, text="Passord:").pack(pady=(12, 4))
    password_entry = ttk.Entry(login_window, width=30, show="*")
    password_entry.pack()

    def submit_login() -> None:
        global uid, username
        entered_username = username_entry.get().strip()
        password = password_entry.get()

        if not entered_username or not password:
            log_event("auth.login_failed", {"reason": "missing_fields"})
            messagebox.showerror(
                "Innlogging", "Fyll inn både brukernavn og passord.", parent=login_window
            )
            return

        if supabase_client.is_enabled():
            try:
                cloud_user = supabase_client.authenticate(
                    "login", entered_username, password
                )
            except supabase_client.SupabaseError as error:
                log_event("auth.login_failed", {"reason": "supabase"})
                messagebox.showerror(
                    "Innlogging",
                    f"Kunne ikke logge inn via Supabase: {error}",
                    parent=login_window,
                )
                return
            user_id = cloud_user.get("user_id")
            saved_username = cloud_user.get("username")
            if not isinstance(user_id, str) or not isinstance(saved_username, str):
                supabase_client.clear_session()
                messagebox.showerror(
                    "Innlogging",
                    "Brukerprofilen i Supabase mangler gyldige opplysninger.",
                    parent=login_window,
                )
                return
            uid = user_id
            username = saved_username
            remember_jonas_session(login_window, user_id)
            start_session("password")
            log_event("auth.login_succeeded", {"login_method": "password"})
            messagebox.showinfo(
                "Innlogging",
                f"Velkommen, {saved_username}!",
                parent=login_window,
            )
            login_window.destroy()
            main(parent)
            return

        users = read_users(login_window)
        if users is None:
            return

        for user in users:
            saved_username = user.get("username")
            saved_password = user.get("password")
            if (
                isinstance(saved_username, str)
                and isinstance(saved_password, str)
                and saved_username.casefold() == entered_username.casefold()
                and saved_password == password
            ):
                user_id = user.get("user_id")
                if not isinstance(user_id, str):
                    log_event("auth.login_failed", {"reason": "invalid_user_id"})
                    messagebox.showerror(
                        "Innlogging",
                        "Brukerkontoen mangler en gyldig bruker-ID.",
                        parent=login_window,
                    )
                    return
                uid = user_id
                username = saved_username
                start_session("password")
                log_event("auth.login_succeeded", {"login_method": "password"})
                messagebox.showinfo(
                    "Innlogging",
                    f"Velkommen, {saved_username}!",
                    parent=login_window,
                )
                login_window.destroy()
                main(parent)
                return

        log_event("auth.login_failed", {"reason": "invalid_credentials"})
        messagebox.showerror(
            "Innlogging",
            "Feil brukernavn eller passord.",
            parent=login_window,
        )

    ttk.Button(login_window, text="Logg inn", command=submit_login).pack(pady=16)
    password_entry.bind("<Return>", lambda _event: submit_login())
    username_entry.focus_set()

def register(parent: tk.Misc) -> None:
    register_window = open_window(parent)
    register_window.title("Registrer deg")
    register_window.geometry("320x260")
    register_window.resizable(False, False)

    tk.Label(register_window, text="Velg brukernavn:").pack(pady=(18, 4))
    username_entry = ttk.Entry(register_window, width=30)
    username_entry.pack()

    tk.Label(register_window, text="Velg passord:").pack(pady=(12, 4))
    password_entry = ttk.Entry(register_window, width=30, show="*")
    password_entry.pack()

    def create_account() -> None:
        global uid, username
        entered_username = username_entry.get().strip()
        password = password_entry.get()

        if not entered_username or not password:
            messagebox.showerror(
                "Registrering",
                "Fyll inn både brukernavn og passord.",
                parent=register_window,
            )
            return

        if supabase_client.is_enabled():
            try:
                cloud_user = supabase_client.authenticate(
                    "register", entered_username, password
                )
            except supabase_client.SupabaseError as error:
                messagebox.showerror(
                    "Registrering",
                    f"Kunne ikke opprette brukeren i Supabase: {error}",
                    parent=register_window,
                )
                return
            user_id = cloud_user.get("user_id")
            saved_username = cloud_user.get("username")
            if not isinstance(user_id, str) or not isinstance(saved_username, str):
                supabase_client.clear_session()
                messagebox.showerror(
                    "Registrering",
                    "Supabase opprettet ikke en gyldig brukerprofil.",
                    parent=register_window,
                )
                return
            uid = user_id
            username = saved_username
            remember_jonas_session(register_window, user_id)
            start_session("registration")
            log_event("account.created")
            log_event("auth.login_succeeded", {"login_method": "registration"})
            messagebox.showinfo(
                "Registrering",
                "Brukeren er opprettet og lagret sikkert i Supabase.",
                parent=register_window,
            )
            register_window.destroy()
            main(parent)
            return

        users = read_users(register_window)
        if users is None:
            return

        for user in users:
            saved_username = user.get("username")
            if (
                isinstance(saved_username, str)
                and saved_username.casefold() == entered_username.casefold()
            ):
                messagebox.showerror(
                    "Registrering",
                    "Brukernavnet er allerede tatt.",
                    parent=register_window,
                )
                return

        existing_ids = {user.get("user_id") for user in users}
        user_id = str(secrets.randbelow(900000) + 100000)
        while user_id in existing_ids:
            user_id = str(secrets.randbelow(900000) + 100000)

        new_user: dict[str, object] = {
            "username": entered_username,
            "password": password,
            "user_id": user_id,
            "token": None,
            "stats": {
                "points": 0,
                "wrong-answers": 0,
                "correct-answers": 0,
                "total-questions": 0,
            },
            "last_sequence": [],
        }

        try:
            log_event(
                "storage.write_started",
                {
                    "backend": "local_jsonl",
                    "resource": USERS_FILE.name,
                    "operation": "append",
                },
            )
            with USERS_FILE.open("a", encoding="utf-8") as file:
                file.write(json.dumps(new_user, ensure_ascii=False) + "\n")
        except OSError as error:
            log_event(
                "storage.write_failed",
                {
                    "backend": "local_jsonl",
                    "resource": USERS_FILE.name,
                    "operation": "append",
                    "error_type": type(error).__name__,
                },
            )
            messagebox.showerror(
                "Registrering",
                f"Kunne ikke lagre brukeren: {error}",
                parent=register_window,
            )
            return

        log_event(
            "storage.write_completed",
            {
                "backend": "local_jsonl",
                "resource": USERS_FILE.name,
                "operation": "append",
            },
        )
        log_event("account.created")
        messagebox.showinfo(
            "Registrering",
            f"Brukeren er opprettet. Din bruker-ID er {user_id}.",
            parent=register_window,
        )
        uid = user_id
        username = entered_username
        start_session("registration")
        log_event("auth.login_succeeded", {"login_method": "registration"})
        register_window.destroy()
        main(parent)

    ttk.Button(
        register_window,
        text="Opprett bruker",
        command=create_account,
    ).pack(pady=18)
    username_entry.focus_set()

def insert_token(parent: tk.Misc) -> None:
    insert_token_window = open_window(parent)
    insert_token_window.title("Logg inn med innloggingstoken")
    insert_token_window.geometry("320x180")
    insert_token_window.resizable(False, False)

    tk.Label(insert_token_window, text="Innloggingstoken:").pack(pady=(18, 4))
    token_entry = ttk.Entry(insert_token_window, width=36, show="*")
    token_entry.pack()

    def submit_token() -> None:
        global uid, username
        if supabase_client.is_enabled():
            messagebox.showerror(
                "Innlogging",
                "Innloggingstoken støttes ikke for Supabase-kontoer ennå. "
                "Logg inn med brukernavn og passord.",
                parent=insert_token_window,
            )
            return
        token = token_entry.get().strip()
        if not token:
            log_event("auth.login_failed", {"reason": "missing_token"})
            messagebox.showerror(
                "Innlogging",
                "Skriv inn innloggingstokenet.",
                parent=insert_token_window,
            )
            return

        users = read_users(insert_token_window)
        if users is None:
            return

        for user in users:
            if user.get("token") == token:
                user_id = user.get("user_id")
                saved_username = user.get("username")
                if not isinstance(user_id, str) or not isinstance(saved_username, str):
                    continue
                uid = user_id
                username = saved_username
                start_session("token")
                log_event("auth.login_succeeded", {"login_method": "token"})
                messagebox.showinfo("Innlogging", "Du er logget inn.", parent=insert_token_window)
                insert_token_window.destroy()
                if app_root is None:
                    raise RuntimeError("Tkinter-vinduet er ikke startet.")
                main(app_root)
                return

        log_event("auth.login_failed", {"reason": "invalid_token"})
        messagebox.showerror(
            "Innlogging",
            "Ugyldig innloggingstoken.",
            parent=insert_token_window,
        )

    ttk.Button(insert_token_window, text="Logg inn", command=submit_token).pack(pady=16)
    token_entry.bind("<Return>", lambda _event: submit_token())
    token_entry.focus_set()

try:
    AUTO_LOGIN_JONAS, JONAS_USER_ID = load_app_config()
except ValueError as error:
    config_error_root = tk.Tk()
    config_error_root.withdraw()
    messagebox.showerror(
        "Konfigurasjonsfeil",
        str(error),
        parent=config_error_root,
    )
    config_error_root.destroy()
else:
    login_tk_page()