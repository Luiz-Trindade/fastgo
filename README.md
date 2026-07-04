# 🚀 FastGo

[![PyPI version](https://badge.fury.io/py/fastgo.svg)](https://badge.fury.io/py/fastgo)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastgo.svg)](https://pypi.org/project/fastgo/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Downloads](https://static.pepy.tech/badge/fastgo)](https://pepy.tech/project/fastgo)
[![GitHub last commit](https://img.shields.io/github/last-commit/seu-usuario/fastgo)](https://github.com/seu-usuario/fastgo)

**FastGo** é um mini‑framework Python construído sobre o **FastAPI** que combina:

- ⚡ **Cache automático** com `diskcache`
- 🗜️ **Compressão GZIP** integrada
- 🗄️ **ORM** via `SQLModel` e `SQLAlchemy`
- 👥 **Workers** baseados no número de CPUs (em produção)
- 📚 **Documentação OpenAPI** automática (`/docs` e `/redoc`)
- 🔄 **Múltiplos workers** com auto‑descoberta da instância

Ele foi projetado para acelerar o desenvolvimento de APIs REST, oferecendo uma base sólida e produtiva com o mínimo de cerimônia.

---

## 📖 Sumário

- [✨ Características](#-características)
- [📦 Instalação](#-instalação)
- [🧱 Estrutura básica](#-estrutura-básica-de-um-projeto)
- [🚀 Exemplo rápido](#-exemplo-rápido-crud-manual)
- [🔄 Geração automática de CRUD](#-geração-automática-de-crud-opcional)
- [🧠 Como funciona o cache](#-como-funciona-o-cache)
- [📁 Modelo base `FastModel`](#-modelo-base-fastmodel)
- [⚙️ Configuração do `FastGo`](#️-configuração-do-fastgo)
- [▶️ Rodando o servidor](#️-rodando-o-servidor)
- [🧪 Testando com `curl`](#-testando-com-curl)
- [🤝 Contribuição](#-contribuição)
- [📄 Licença](#-licença)

---

## ✨ Características

- **🧠 Cache inteligente** – rotas `GET` são cacheadas em disco por padrão (TTL configurável).
- **🔄 Invalidação automática** – qualquer rota de escrita (`POST`, `PUT`, `PATCH`, `DELETE`) invalida as chaves de cache com prefixo compatível.
- **🗜️ GZIP** – compressão de respostas maiores que 1KB (nível 9) integrada.
- **🗄️ ORM com SQLModel** – definição de modelos com tipagem forte e validação Pydantic.
- **🔧 Métodos auxiliares** – `save()`, `delete()`, `update()`, `find()`, `find_all()`, `find_one()`, `count()`, `create()` e `bulk_create()`.
- **🧩 Geração automática de esquemas** – modelos `Create` e `Update` são criados dinamicamente (quando se usa `register_model`).
- **📄 Documentação interativa** – Swagger UI (`/docs`) e ReDoc (`/redoc`) a partir do FastAPI.
- **👥 Múltiplos workers** – em produção, inicia um worker por núcleo de CPU (detectado automaticamente).
- **⚡ Preparado para produção** – usa `uvloop` para melhor performance.

---

## 📦 Instalação

Com `uv` (recomendado):

```bash
uv add fastgo
```

Ou com `pip`:

```bash
pip install fastgo
```

> **Dependências principais:** `fastapi`, `uvicorn`, `sqlmodel`, `diskcache`, `uvloop`.

---

## 🧱 Estrutura básica de um projeto

```
meu_projeto/
├── main.py              # Seu código de aplicação
├── fastgo/              # O framework (pode ser instalado como pacote)
│   ├── core.py          # Classe FastGo
│   └── models.py        # Classe base FastModel
└── fastgo_cache/        # Diretório de cache (criado automaticamente)
```

---

## 🚀 Exemplo rápido (CRUD manual)

O exemplo abaixo demonstra o uso **manual** das rotas CRUD, onde você define os endpoints explicitamente. Esta abordagem oferece máximo controle e é a que você vê no `main.py` fornecido.

### 1. Defina seu modelo

```python
# main.py
from fastgo.core import FastGo
from fastgo.models import FastModel, Field
from sqlmodel import Session, SQLModel, create_engine
from fastapi import Depends, HTTPException
from typing import Optional

class Product(FastModel, table=True):
    name: str = Field(nullable=False, description="Nome do produto")
    price: float = Field(nullable=False, description="Preço do produto")
    stock: int = Field(default=0, nullable=False, description="Quantidade em estoque")
```

### 2. Crie os modelos de entrada (Create / Update)

```python
class ProductCreate(SQLModel):
    name: str
    price: float
    stock: int = 0

class ProductUpdate(SQLModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
```

### 3. Inicialize o FastGo e a sessão do banco

```python
fg = FastGo(database_url="sqlite:///fastgo.db", database_models=[Product])

def get_session():
    with Session(fg.engine) as session:
        yield session
```

### 4. Registre as rotas CRUD manualmente

```python
# Listar (GET /products)
@fg.register_route(
    "/products",
    tags=["Products"],
    summary="Lista todos os produtos",
    response_model=list[Product],
)
def list_products(session: Session = Depends(get_session)):
    return Product.find_all(session)

# Obter (GET /products/{id})
@fg.register_route(
    "/products/{product_id}",
    tags=["Products"],
    summary="Obtém um produto pelo ID",
    response_model=Product,
    responses={404: {"description": "Produto não encontrado"}},
)
def get_product(product_id: int, session: Session = Depends(get_session)):
    product = Product.find(session, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# Criar (POST /products)
@fg.register_route(
    "/products",
    methods=["POST"],
    tags=["Products"],
    summary="Cria um novo produto",
    response_model=Product,
    status_code=201,
)
def create_product(data: ProductCreate, session: Session = Depends(get_session)):
    new_product = Product(**data.dict())
    new_product.save(session)
    return new_product

# Atualizar (PATCH /products/{id})
@fg.register_route(
    "/products/{product_id}",
    methods=["PATCH"],
    tags=["Products"],
    summary="Atualiza parcialmente um produto",
    response_model=Product,
    responses={404: {"description": "Produto não encontrado"}},
)
def update_product(
    product_id: int,
    data: ProductUpdate,
    session: Session = Depends(get_session),
):
    product = Product.find(session, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    update_data = data.dict(exclude_unset=True)
    product.update(session, **update_data)
    return product

# Deletar (DELETE /products/{id})
@fg.register_route(
    "/products/{product_id}",
    methods=["DELETE"],
    tags=["Products"],
    summary="Deleta um produto",
    responses={404: {"description": "Produto não encontrado"}},
)
def delete_product(product_id: int, session: Session = Depends(get_session)):
    product = Product.find(session, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.delete(session)
    return {"detail": "Product deleted"}
```

### 5. Inicie o servidor

```python
if __name__ == "__main__":
    fg.run()          # Produção (com workers)
    # fg.run(reload=True)  # Desenvolvimento (hot-reload)
```

### 6. Execute

```bash
uv run main.py
```

Acesse a documentação em `http://localhost:8000/docs`.

---

## 🔄 Geração automática de CRUD (opcional)

Embora o exemplo acima seja manual, o FastGo também oferece um método `register_model()` que gera **todas as 5 rotas CRUD automaticamente** para qualquer modelo que herde de `FastModel`. Basta fazer:

```python
fg.register_model(Product, tags=["Products"])
```

Isso criará:

| Método   | Rota             | Descrição             |
| :------- | :--------------- | :-------------------- |
| `GET`    | `/products`      | Lista todos           |
| `POST`   | `/products`      | Cria um novo          |
| `GET`    | `/products/{id}` | Obtém um              |
| `PATCH`  | `/products/{id}` | Atualiza parcialmente |
| `DELETE` | `/products/{id}` | Deleta                |

Os modelos `ProductCreate` e `ProductUpdate` são gerados dinamicamente a partir dos campos do modelo, exceto `id`, `created_at` e `updated_at`.

---

## 🧠 Como funciona o cache

- **Ativado por padrão** para todas as rotas `GET` (TTL padrão = 120 segundos).
- **Chave de cache**: `{prefixo}:{nome_função}:{argumentos_serializados}`, ignorando objetos `Request` e `Session`.
- **Invalidação automática**: qualquer rota com `methods` contendo `POST`, `PUT`, `PATCH` ou `DELETE` invalida todas as chaves cujo prefixo corresponda ao caminho da rota.
- Você pode desabilitar o cache por rota com `cache=False`.

---

## 📁 Modelo base `FastModel`

A classe `FastModel` herda de `SQLModel` e fornece os seguintes campos e métodos:

**Campos:**

- `id: int` (chave primária)
- `created_at: datetime` (UTC, preenchido automaticamente)
- `updated_at: datetime` (UTC, atualizado a cada modificação)

**Métodos de instância:**

- `save(session)` – insere/atualiza a instância
- `delete(session)` – remove a instância
- `update(session, **kwargs)` – atualiza campos e salva

**Métodos de classe:**

- `find(session, id)` – busca por ID
- `find_all(session, **filters)` – lista com filtros opcionais
- `find_one(session, **filters)` – primeiro registro que atende aos filtros
- `count(session, **filters)` – contagem
- `create(session, **data)` – cria e salva
- `bulk_create(session, items)` – inserção em lote

---

## ⚙️ Configuração do `FastGo`

| Parâmetro         | Padrão                             | Descrição                                                 |
| :---------------- | :--------------------------------- | :-------------------------------------------------------- |
| `database_url`    | `"sqlite:///fastgo.db"`            | URL do banco de dados (suporta SQLite, PostgreSQL, MySQL) |
| `database_models` | `[]`                               | Lista de modelos SQLModel para criar as tabelas           |
| `cache_ttl`       | `120`                              | Tempo de vida do cache (segundos)                         |
| `cache_dir`       | `"fastgo_cache"`                   | Diretório onde o cache em disco será armazenado           |
| `title`           | `"FastGo API"`                     | Título da documentação OpenAPI                            |
| `description`     | `"API desenvolvida com FastGo..."` | Descrição da API                                          |
| `version`         | `"1.0.0"`                          | Versão da API                                             |
| `docs_url`        | `"/docs"`                          | URL do Swagger UI                                         |
| `redoc_url`       | `"/redoc"`                         | URL do ReDoc                                              |

---

## ▶️ Rodando o servidor

**Desenvolvimento (com hot‑reload):**

```python
fg.run(reload=True)
```

**Produção (com múltiplos workers):**

```python
fg.run(host="0.0.0.0", port=8080)
```

O número de workers será `cpu_count()` por padrão (ou 1 se não for detectado). Você pode sobrescrever com `workers=4`.

---

## 🧪 Testando com `curl`

```bash
# Criar um produto
curl -X POST "localhost:8000/products" \
     -H "Content-Type: application/json" \
     -d '{"name": "Notebook", "price": 3500.0, "stock": 10}'

# Listar produtos
curl "localhost:8000/products"

# Atualizar parcialmente
curl -X PATCH "localhost:8000/products/1" \
     -H "Content-Type: application/json" \
     -d '{"price": 3200.0}'

# Deletar
curl -X DELETE "localhost:8000/products/1"
```

---

## 🤝 Contribuição

Sinta‑se à vontade para abrir _issues_ e _pull requests_. O FastGo está em evolução constante e toda colaboração é bem‑vinda.

---

## 📄 Licença

Este projeto é distribuído sob a licença MIT. Consulte o arquivo `LICENSE` para mais detalhes.

---

**FastGo** – porque construir APIs não precisa ser complicado. 🚀
# fastgo
