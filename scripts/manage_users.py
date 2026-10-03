import sys
import os
import getpass
import secrets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.credentials import load_or_init_config, save_config, add_user, RegisterError, hash_password

USAGE = """Usage:
  python3 scripts/manage_users.py add <username> "<Full Name>" <email>
  python3 scripts/manage_users.py set-password <username>
  python3 scripts/manage_users.py remove <username>
  python3 scripts/manage_users.py list
  python3 scripts/manage_users.py regenerate-api-key"""


def prompt_password():
    password = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords don't match.")
        sys.exit(1)
    return password


def cmd_add(username, name, email):
    config = load_or_init_config()
    if username in config["credentials"]["usernames"]:
        print(f"User '{username}' already exists. Use set-password to change their password.")
        sys.exit(1)
    password = prompt_password()
    try:
        add_user(config, username, name, email, password)
    except RegisterError as e:
        print(str(e))
        sys.exit(1)
    print(f"Added user '{username}'.")


def cmd_set_password(username):
    config = load_or_init_config()
    if username not in config["credentials"]["usernames"]:
        print(f"No such user: {username}")
        sys.exit(1)
    password = prompt_password()
    config["credentials"]["usernames"][username]["password"] = hash_password(password)
    save_config(config)
    print(f"Password updated for '{username}'.")


def cmd_remove(username):
    config = load_or_init_config()
    if username in config["credentials"]["usernames"]:
        del config["credentials"]["usernames"][username]
        save_config(config)
        print(f"Removed '{username}'.")
    else:
        print(f"No such user: {username}")


def cmd_list():
    config = load_or_init_config()
    users = config["credentials"]["usernames"]
    if not users:
        print("No users configured.")
        return
    for uname, info in users.items():
        print(f"- {uname}  ({info.get('name', '')}, {info.get('email', '')})")


def cmd_regenerate_api_key():
    config = load_or_init_config()
    config["api"]["secret_key"] = secrets.token_hex(32)
    save_config(config)
    print("API signing key regenerated — all existing tokens are now invalid; log in again to get new ones.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(USAGE)
        sys.exit(1)

    cmd = args[0]
    if cmd == "add" and len(args) == 4:
        cmd_add(args[1], args[2], args[3])
    elif cmd == "set-password" and len(args) == 2:
        cmd_set_password(args[1])
    elif cmd == "remove" and len(args) == 2:
        cmd_remove(args[1])
    elif cmd == "list" and len(args) == 1:
        cmd_list()
    elif cmd == "regenerate-api-key" and len(args) == 1:
        cmd_regenerate_api_key()
    else:
        print(USAGE)
        sys.exit(1)
