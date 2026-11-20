"""CLI: python -m app.admin.cli create EMAIL

The password is never taken from argv or logged: it is prompted (twice) on a terminal, or read
as one line from stdin when piped (for scripted/dev use).
"""

import argparse
import getpass
import sys

import psycopg

from app.config import get_settings

from . import auth, sql


def read_password() -> str:
    if sys.stdin.isatty():
        first = getpass.getpass("Пароль: ")
        if getpass.getpass("Повторите пароль: ") != first:
            raise SystemExit("Пароли не совпадают")
        return first
    return sys.stdin.readline().rstrip("\r\n")


def create_admin(conninfo: str, email: str, password: str) -> str:
    err = password_check(password)
    if err:
        raise SystemExit(err)
    email = auth.normalize_email(email)
    if "@" not in email or len(email) < 3:
        raise SystemExit("Некорректный e-mail")
    with psycopg.connect(conninfo) as conn:
        exists = conn.execute(sql.ADMIN_BY_EMAIL, (email,)).fetchone()
        if exists:
            raise SystemExit(f"Админ {email} уже существует")
        conn.execute(sql.ADMIN_INSERT, (email, auth.hash_password(password)))
    return email


def password_check(password: str):
    return auth.password_error(password)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="app.admin.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    create = sub.add_parser("create", help="create an admin account")
    create.add_argument("email")
    args = parser.parse_args(argv)
    if args.cmd == "create":
        password = read_password()
        email = create_admin(get_settings().database_url, args.email, password)
        print(f"Админ создан: {email}")


if __name__ == "__main__":
    main()
