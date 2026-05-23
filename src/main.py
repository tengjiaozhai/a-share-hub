import argparse
from fastapi import FastAPI
from src.api.routes_health import router as health_router

def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    return app

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="serve")
    parser.parse_args()

if __name__ == "__main__":
    main()
