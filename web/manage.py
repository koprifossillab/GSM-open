#!/usr/bin/env python
"""Django 관리 명령 입구."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gsmweb.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
