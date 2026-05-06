if __name__ == "__main__":
    try:
        print("[startup] importing web server modules...", flush=True)
        from web_app.server import run

        print("[startup] web server modules imported", flush=True)
        run()
    except Exception as exc:
        print(f"[startup] failed: {exc}", flush=True)
        raise SystemExit(str(exc))
