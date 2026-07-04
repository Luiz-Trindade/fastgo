# 🚀 FastGo

[![PyPI version](https://badge.fury.io/py/fastgo.svg)](https://badge.fury.io/py/fastgo)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastgo.svg)](https://pypi.org/project/fastgo/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Downloads](https://static.pepy.tech/badge/fastgo)](https://pepy.tech/project/fastgo)

**FastGo** é um microframework Python construído sobre o **FastAPI** que gera automaticamente **CRUD completo**, **cache inteligente** e **documentação OpenAPI** com apenas algumas linhas de código.

---

## ✨ Características

- ⚡ **CRUD automático** – registre um modelo e ganhe 5 rotas prontas (`list`, `create`, `read`, `update`, `delete`)
- 🧠 **Cache em disco** – rotas `GET` cacheadas por padrão (TTL configurável)
- 🔄 **Invalidação automática** – escritas (`POST`, `PUT`, `PATCH`, `DELETE`) invalidam o cache
- 🗜️ **Compressão GZIP** – respostas > 1KB comprimidas (nível 9)
- 🗄️ **ORM com SQLModel** – tipagem forte, validação Pydantic e métodos auxiliares (`save`, `find`, etc.)
- 📚 **Documentação interativa** – Swagger UI (`/docs`) e ReDoc (`/redoc`) automáticos
- 👥 **Múltiplos workers** – em produção, um worker por núcleo de CPU (usando `uvloop`)
- 🔌 **Extensível** – você ainda pode registrar rotas customizadas manualmente

---

## 📦 Instalação

```bash
pip install fastgo
```

ou com `uv`:

```bash
uv add fastgo
```

---

## 🚀 Exemplo mínimo

```python
from fastgo import FastGo, FastModel, Field

class Product(FastModel, table=True):
    name: str = Field(nullable=False)
    price: float = Field(nullable=False)
    stock: int = Field(default=0)

fg = FastGo(database_url="sqlite:///fastgo.db", database_models=[Product])
fg.register_model(Product, tags=["Products"])

if __name__ == "__main__":
    fg.run()
```

Com isso, você já tem:

| Método   | Rota             | Descrição             |
| :------- | :--------------- | :-------------------- |
| `GET`    | `/products`      | Lista todos           |
| `POST`   | `/products`      | Cria um novo          |
| `GET`    | `/products/{id}` | Obtém um              |
| `PATCH`  | `/products/{id}` | Atualiza parcialmente |
| `DELETE` | `/products/{id}` | Deleta                |

Acesse a documentação interativa em `http://localhost:8000/docs`.

---

## 🧠 Como funciona o cache

- **Ativado por padrão** em todas as rotas `GET` (TTL = 120s).
- **Chave**: `{prefixo}:{função}:{argumentos}` – ignora `Request` e `Session` para evitar erros.
- **Invalidação automática**: qualquer rota de escrita (`POST`, `PUT`, `PATCH`, `DELETE`) invalida as chaves que começam com o prefixo da rota (ex: `/products`).
- Desabilite o cache por rota com `cache=False`.

---

## 📁 Modelo base `FastModel`

A classe `FastModel` herda de `SQLModel` e adiciona:

- **Campos automáticos**: `id`, `created_at`, `updated_at` (UTC)
- **Métodos de instância**: `save()`, `delete()`, `update(**kwargs)`
- **Métodos de classe**: `find()`, `find_all()`, `find_one()`, `count()`, `create()`, `bulk_create()`

---

## ⚙️ Configuração do `FastGo`

| Parâmetro         | Padrão                  | Descrição                                |
| :---------------- | :---------------------- | :--------------------------------------- |
| `database_url`    | `"sqlite:///fastgo.db"` | URL do banco (SQLite, PostgreSQL, MySQL) |
| `database_models` | `[]`                    | Lista de modelos para criar as tabelas   |
| `cache_ttl`       | `120`                   | TTL do cache em segundos                 |
| `cache_dir`       | `"fastgo_cache"`        | Diretório do cache em disco              |
| `title`           | `"FastGo API"`          | Título da documentação OpenAPI           |
| `version`         | `"1.0.0"`               | Versão da API                            |
| `docs_url`        | `"/docs"`               | URL do Swagger UI                        |

---

## ▶️ Rodando o servidor

**Desenvolvimento (hot‑reload):**

```python
fg.run(reload=True)
```

**Produção (com workers):**

```python
fg.run(host="0.0.0.0", port=8080)
```

O número de workers é `cpu_count()` por padrão (ou 1). Você pode sobrescrever com `workers=4`.

---

## 🧪 Teste com `curl`

```bash
# Criar
curl -X POST localhost:8000/products \
  -H "Content-Type: application/json" \
  -d '{"name": "Notebook", "price": 3500, "stock": 10}'

# Listar
curl localhost:8000/products

# Atualizar
curl -X PATCH localhost:8000/products/1 \
  -H "Content-Type: application/json" \
  -d '{"price": 3200}'

# Deletar
curl -X DELETE localhost:8000/products/1
```

---

## 🔧 Rotas customizadas

Você ainda pode registrar rotas manuais normalmente:

```python
@fg.register_route("/health", tags=["System"])
def health():
    return {"status": "ok"}
```

---

## 📄 Licença

MIT. Veja o arquivo `LICENSE` para mais detalhes.

---

**FastGo** – porque construir APIs não precisa ser complicado. 🚀
