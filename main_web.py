from web_app.server import run


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        raise SystemExit(str(exc))
