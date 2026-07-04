import sys
import inspect
import uvicorn
import json
from os import cpu_count
from functools import wraps
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from diskcache import Cache
from typing import Callable, Optional, Any, Dict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from sqlmodel import create_engine, SQLModel, Session


class FastGo:
    def __init__(
        self,
        database_url: str = "sqlite:///fastgo.db",
        database_models: Optional[list] = None,
        cache_ttl: int = 120,
        cache_dir: str = "cache",
        # Parâmetros para personalizar a documentação OpenAPI
        title: str = "FastGo API",
        description: str = "API desenvolvida com FastGo (FastAPI + cache automático)",
        version: str = "1.0.0",
        openapi_url: Optional[str] = "/openapi.json",
        docs_url: Optional[str] = "/docs",
        redoc_url: Optional[str] = "/redoc",
        **fastapi_kwargs,
    ):
        # Cria a aplicação FastAPI com os metadados fornecidos
        self.app = FastAPI(
            title=title,
            description=description,
            version=version,
            openapi_url=openapi_url,
            docs_url=docs_url,
            redoc_url=redoc_url,
            **fastapi_kwargs,
        )
        self.app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=9)

        # --- Configuração do banco de dados ---
        self.database_url = database_url
        self.database_models = database_models or []
        self.engine = None

        if self.database_models:
            self.engine = create_engine(
                self.database_url, echo=True
            )  # echo=True para ver SQL
            SQLModel.metadata.create_all(self.engine)
            print(
                f"✅ Tabelas criadas/verificadas para: {[m.__name__ for m in self.database_models]}"
            )

        # --- Cache e workers ---
        self.cache = Cache(cache_dir)
        self.default_workers = cpu_count() or 1
        self.default_cache_ttl = cache_ttl
        self._cache_prefixes = set()  # prefixos que devem ser invalidados após escrita

        # Middleware para invalidar cache automaticamente após requisições de escrita
        self.app.add_middleware(CacheInvalidationMiddleware, fastgo=self)

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

    def register_route(self, path: str, **kwargs):
        """
        Registra uma rota.

        Parâmetros opcionais via kwargs (repassados ao FastAPI):
        - methods: list (verbos HTTP, padrão ["GET"])
        - cache_ttl: int (tempo de vida do cache, apenas para GET)
        - cache: bool (se False, desabilita cache mesmo para GET)
        - cache_prefix: str (prefixo para agrupar e invalidar, padrão = path)
        - tags: list (para agrupar na documentação)
        - summary: str (resumo da rota)
        - description: str (descrição detalhada)
        - response_model: Modelo Pydantic para resposta
        - responses: dict (respostas adicionais)
        - operation_id: str
        - deprecated: bool
        """
        cache_ttl = kwargs.pop("cache_ttl", self.default_cache_ttl)
        cache_enabled = kwargs.pop("cache", True)
        cache_prefix = kwargs.pop("cache_prefix", path.rstrip("/"))
        methods = kwargs.get("methods", ["GET"])
        is_write = any(m in ["POST", "PUT", "DELETE", "PATCH"] for m in methods)

        def decorator(endpoint: Callable):
            # Se for rota de escrita ou cache desabilitado, registra sem cache
            if is_write or not cache_enabled:
                if "methods" not in kwargs:
                    kwargs["methods"] = ["GET"]
                self.app.add_api_route(path, endpoint, **kwargs)
                if is_write:
                    self._cache_prefixes.add(cache_prefix)
                return endpoint

            # Rota GET com cache
            @wraps(endpoint)
            async def cached_endpoint(*args, **kwargs):
                sig = inspect.signature(endpoint)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()

                # 🔥 CORREÇÃO: Remove parâmetros do tipo Request e Session
                for name, value in list(bound.arguments.items()):
                    if isinstance(value, (Request, Session)):  # <-- ADICIONADO Session
                        del bound.arguments[name]

                items = sorted(bound.arguments.items())
                key_data = f"{endpoint.__name__}:{json.dumps(items, sort_keys=True)}"
                full_key = f"{cache_prefix}:{key_data}"

                cached = self.cache.get(full_key)
                if cached is not None:
                    return cached

                if inspect.iscoroutinefunction(endpoint):
                    result = await endpoint(*args, **kwargs)
                else:
                    result = endpoint(*args, **kwargs)

                self.cache.set(full_key, result, expire=cache_ttl)
                return result

            if "methods" not in kwargs:
                kwargs["methods"] = ["GET"]
            self.app.add_api_route(path, cached_endpoint, **kwargs)
            return endpoint

        return decorator

    def invalidate_cache_prefix(self, prefix: str):
        """Remove todas as chaves de cache que começam com o prefixo."""
        for key in list(self.cache.iterkeys()):
            if key.startswith(prefix):
                self.cache.delete(key)

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
        workers: Optional[int] = None,
        **kwargs,
    ):
        if reload:
            uvicorn.run(
                self.app, host=host, port=port, reload=True, loop="uvloop", **kwargs
            )
        else:
            main_module = sys.modules.get("__main__")
            app_str = None
            if main_module:
                for var_name, obj in inspect.getmembers(main_module):
                    if obj is self:
                        app_str = f"{main_module.__name__}:{var_name}"
                        break
            if app_str:
                if workers is None:
                    workers = self.default_workers
                uvicorn.run(
                    app_str,
                    host=host,
                    port=port,
                    workers=workers,
                    loop="uvloop",
                    **kwargs,
                )
            else:
                uvicorn.run(self.app, host=host, port=port, loop="uvloop", **kwargs)


class CacheInvalidationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, fastgo):
        super().__init__(app)
        self.fastgo = fastgo

    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            path = request.url.path.rstrip("/")
            for prefix in self.fastgo._cache_prefixes:
                if path.startswith(prefix):
                    self.fastgo.invalidate_cache_prefix(prefix)
        return response
