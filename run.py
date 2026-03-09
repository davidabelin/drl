"""Local entrypoint for the DRL web app."""

from __future__ import annotations

from drl_web import create_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
