import sys
import inspect
import uvicorn
import json
from os import cpu_count
from functools import wraps
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from diskcache import Cache
from typing import Callable, Optional, Any, Dict, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from sqlmodel import create_engine, SQLModel, Session


class FastGo:
    def __init__(
        self,
        database_url: str = "sqlite:///fastgo.db",
        database_models: Optional[List[SQLModel]] = None,
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

                # Remove parâmetros do tipo Request e Session
                for name, value in list(bound.arguments.items()):
                    if isinstance(value, (Request, Session)):
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

    def register_model(
        self,
        model_class,
        prefix: Optional[str] = None,
        exclude: Optional[List[str]] = None,
        **route_kwargs,
    ):
        """
        Registra automaticamente rotas CRUD para um modelo.

        Args:
            model_class: Classe que herda de FastModel (ex: Product)
            prefix: Prefixo para as rotas (padrão: nome do modelo em minúsculo + 's')
            exclude: Lista de métodos a excluir ('list', 'create', 'read', 'update', 'delete')
            **route_kwargs: Parâmetros extras para todas as rotas (ex: tags=["Products"])
        """
        # Define o prefixo padrão (ex: Product -> /products)
        if prefix is None:
            prefix = f"/{model_class.__name__.lower()}s"

        exclude = exclude or []
        exclude_set = set(exclude)

        # --- Cria a engine se ainda não existir ---
        if self.engine is None:
            self.engine = create_engine(self.database_url, echo=True)
            SQLModel.metadata.create_all(self.engine)
            print(f"✅ Tabelas criadas/verificadas para: {model_class.__name__}")

        # --- Cria modelos Pydantic para entrada de dados (criação e atualização) ---
        # Identifica campos que não fazem parte da criação/atualização
        ignored_fields = {"id", "created_at", "updated_at"}

        # Obtém campos do modelo (Pydantic v2)
        fields_info = {}
        for name, field in model_class.model_fields.items():
            if name not in ignored_fields:
                fields_info[name] = (field.annotation, field)

        # Modelo de criação (todos os campos obrigatórios)
        create_annotations = {k: v[0] for k, v in fields_info.items()}
        create_defaults = {
            k: v[1].default for k, v in fields_info.items() if v[1].default is not None
        }
        # Cria a classe dinamicamente
        CreateModel = type(
            f"{model_class.__name__}Create",
            (SQLModel,),
            {
                "__annotations__": create_annotations,
                **create_defaults,
            },
        )

        # Modelo de atualização (todos os campos opcionais)
        from typing import Optional as OptType

        update_annotations = {k: OptType[v[0]] for k, v in fields_info.items()}
        update_defaults = {k: None for k in fields_info}
        UpdateModel = type(
            f"{model_class.__name__}Update",
            (SQLModel,),
            {
                "__annotations__": update_annotations,
                **update_defaults,
            },
        )

        # Dependência para obter sessão
        def get_session():
            with Session(self.engine) as session:
                yield session

        # --- Registro das rotas ---

        # 1. Listar (GET /{prefix})
        if "list" not in exclude_set:

            @self.register_route(
                prefix,
                methods=["GET"],
                response_model=list[model_class],
                cache_prefix=prefix,
                **route_kwargs,
            )
            def list_items(session: Session = Depends(get_session)):
                return model_class.find_all(session)

            list_items.__name__ = f"list_{model_class.__name__.lower()}"

        # 2. Criar (POST /{prefix})
        if "create" not in exclude_set:

            @self.register_route(
                prefix,
                methods=["POST"],
                response_model=model_class,
                status_code=201,
                cache_prefix=prefix,
                **route_kwargs,
            )
            def create_item(data: CreateModel, session: Session = Depends(get_session)):
                new_item = model_class(**data.model_dump())
                new_item.save(session)
                return new_item

            create_item.__name__ = f"create_{model_class.__name__.lower()}"

        # 3. Obter (GET /{prefix}/{id})
        if "read" not in exclude_set:

            @self.register_route(
                f"{prefix}/{{item_id}}",
                methods=["GET"],
                response_model=model_class,
                cache_prefix=prefix,
                **route_kwargs,
            )
            def get_item(item_id: int, session: Session = Depends(get_session)):
                item = model_class.find(session, item_id)
                if not item:
                    raise HTTPException(status_code=404, detail="Item not found")
                return item

            get_item.__name__ = f"get_{model_class.__name__.lower()}"

        # 4. Atualizar (PATCH /{prefix}/{id})
        if "update" not in exclude_set:

            @self.register_route(
                f"{prefix}/{{item_id}}",
                methods=["PATCH"],
                response_model=model_class,
                cache_prefix=prefix,
                **route_kwargs,
            )
            def update_item(
                item_id: int,
                data: UpdateModel,
                session: Session = Depends(get_session),
            ):
                item = model_class.find(session, item_id)
                if not item:
                    raise HTTPException(status_code=404, detail="Item not found")
                update_data = data.model_dump(exclude_unset=True)
                item.update(session, **update_data)
                return item

            update_item.__name__ = f"update_{model_class.__name__.lower()}"

        # 5. Deletar (DELETE /{prefix}/{id})
        if "delete" not in exclude_set:

            @self.register_route(
                f"{prefix}/{{item_id}}",
                methods=["DELETE"],
                cache_prefix=prefix,
                **route_kwargs,
            )
            def delete_item(item_id: int, session: Session = Depends(get_session)):
                item = model_class.find(session, item_id)
                if not item:
                    raise HTTPException(status_code=404, detail="Item not found")
                item.delete(session)
                return {"detail": "Item deleted"}

            delete_item.__name__ = f"delete_{model_class.__name__.lower()}"

        print(f"✅ Rotas CRUD registradas para {model_class.__name__} em {prefix}")

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
