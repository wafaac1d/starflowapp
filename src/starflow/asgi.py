from fastapi import FastAPI

from starflow.api.app import build_fastapi
from starflow.bootstrap import build_container
from starflow.config import Settings


def create_app() -> FastAPI:
    return build_fastapi(build_container(Settings()))
