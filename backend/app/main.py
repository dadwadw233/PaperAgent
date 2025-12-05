from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import create_db_engine, init_db
from .routers import papers, config, chat, import_csv, pipeline


def create_app() -> FastAPI:
    app = FastAPI(title="Paper Agent API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(papers.router)
    app.include_router(config.router)
    app.include_router(chat.router)
    app.include_router(import_csv.router)
    app.include_router(pipeline.router)

    return app


app = create_app()

# Initialize DB on import for now; can be moved to startup event later.
init_db(create_db_engine())
