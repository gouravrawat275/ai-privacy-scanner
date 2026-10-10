import os
import re
import secrets

import bcrypt
import yaml

from modules.database import connect_database

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "auth_config.yaml")

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z '-]{0,49}$")


class AuthConfigError(Exception):
    pass


class RegisterError(Exception):
    pass


def _load_database_config():
    conn = connect_database(CONFIG_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_users ("
            "username TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, "
            "password TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_settings ("
            "setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL)"
        )
        setting = conn.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = ?",
            ("api_secret_key",),
        ).fetchone()
        secret_key = setting["setting_value"] if setting else secrets.token_hex(32)
        conn.execute(
            "INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?) "
            "ON CONFLICT (setting_key) DO NOTHING",
            ("api_secret_key", secret_key),
        )
        setting = conn.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = ?",
            ("api_secret_key",),
        ).fetchone()
        user_rows = conn.execute(
            "SELECT username, name, email, password FROM app_users"
        ).fetchall()
        conn.commit()
        return {
            "credentials": {
                "usernames": {
                    row["username"]: {
                        "name": row["name"],
                        "email": row["email"],
                        "password": row["password"],
                    }
                    for row in user_rows
                }
            },
            "api": {
                **_default_config()["api"],
                "secret_key": setting["setting_value"],
            },
        }
    finally:
        conn.close()


def _default_config():
    return {
        "credentials": {"usernames": {}},
        "api": {"secret_key": secrets.token_hex(32), "algorithm": "HS256", "token_expiry_minutes": 60,
                "refresh_token_expiry_days": 30},
    }


def load_config():
    if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL"):
        raise AuthConfigError(
            "DATABASE_URL is required on Vercel. Configure a Neon PostgreSQL connection string."
        )
    if os.environ.get("DATABASE_URL"):
        return _load_database_config()
    if not os.path.exists(CONFIG_PATH):
        raise AuthConfigError(
            "No auth_config.yaml found. Run `python3 scripts/manage_users.py "
            "add <username> \"<Full Name>\" <email>` first."
        )
    with open(CONFIG_PATH) as f:
        raw = yaml.safe_load(f) or {}

    config = {"credentials": {"usernames": {}}, "api": {}}
    for username, entry in raw.get("credentials", {}).get("usernames", {}).items():
        config["credentials"]["usernames"][username] = {
            "name": entry.get("name", ""),
            "email": entry.get("email", username),
            "password": entry["password"],
        }
    config["api"] = {**_default_config()["api"], **raw.get("api", {})}
    if not config["api"].get("secret_key"):
        config["api"]["secret_key"] = secrets.token_hex(32)

    if raw != config:
        save_config(config)
    return config


def load_or_init_config():
    if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL"):
        raise AuthConfigError(
            "DATABASE_URL is required on Vercel. Configure a Neon PostgreSQL connection string."
        )
    if os.environ.get("DATABASE_URL"):
        return _load_database_config()
    if not os.path.exists(CONFIG_PATH):
        return _default_config()
    return load_config()


def save_config(config):
    clean = {
        "credentials": config["credentials"],
        "api": config["api"],
    }
    if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL"):
        raise AuthConfigError(
            "DATABASE_URL is required on Vercel. Configure a Neon PostgreSQL connection string."
        )
    if os.environ.get("DATABASE_URL"):
        conn = connect_database(CONFIG_PATH)
        try:
            conn.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?) "
                "ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value",
                ("api_secret_key", clean["api"]["secret_key"]),
            )
            for username, entry in clean["credentials"]["usernames"].items():
                conn.execute(
                    "INSERT INTO app_users (username, name, email, password) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT (username) DO UPDATE SET name = EXCLUDED.name, "
                    "email = EXCLUDED.email, password = EXCLUDED.password",
                    (
                        username,
                        entry.get("name", ""),
                        entry.get("email", username),
                        entry["password"],
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        return
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(clean, f, default_flow_style=False, allow_unicode=True)


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(username, password, config):
    users = config["credentials"]["usernames"]
    if username not in users:
        return False
    stored_hash = users[username]["password"]
    return bcrypt.checkpw(password.encode(), stored_hash.encode())


def diagnose_password(password):
    if not (8 <= len(password) <= 20):
        return "Password must be 8-20 characters long."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    if not re.search(r"[@$!%*?&]", password):
        return "Password must contain at least one special character (@$!%*?&)."
    return None


def add_user(config, username, name, email, password):
    if not username:
        raise RegisterError("Username is required.")
    if username in config["credentials"]["usernames"]:
        raise RegisterError("Username already taken.")
    if email and not EMAIL_RE.match(email):
        raise RegisterError("Email is not valid.")
    problem = diagnose_password(password)
    if problem:
        raise RegisterError(problem)

    config["credentials"]["usernames"][username] = {
        "name": name,
        "email": email,
        "password": hash_password(password),
    }
    save_config(config)
    return username


def register_user(config, first_name, last_name, email, password, password_confirm):
    if not NAME_RE.match(first_name or ""):
        raise RegisterError("First name is not valid.")
    if not NAME_RE.match(last_name or ""):
        raise RegisterError("Last name is not valid.")
    if not EMAIL_RE.match(email or ""):
        raise RegisterError("Email is not valid.")
    if email in config["credentials"]["usernames"]:
        raise RegisterError("Email already taken.")
    if password != password_confirm:
        raise RegisterError("Passwords do not match.")
    return add_user(config, email, f"{first_name} {last_name}", email, password)
