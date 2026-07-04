from src.fastgo.core import FastGo
from src.fastgo.models import FastModel, Field
from sqlmodel import Session, SQLModel, create_engine
from fastapi import Depends, HTTPException
from typing import Optional


# --- Modelo Product ---
class Product(FastModel, table=True):
    name: str = Field(nullable=False, description="Nome do produto")
    price: float = Field(nullable=False, description="Preço do produto")
    stock: int = Field(default=0, nullable=False, description="Quantidade em estoque")


# --- Modelos para entrada de dados (criação e atualização) ---
class ProductCreate(SQLModel):
    name: str
    price: float
    stock: int = 0


class ProductUpdate(SQLModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None


# --- Inicialização do FastGo ---
fg = FastGo(database_url="sqlite:///fastgo.db", database_models=[Product])


# --- Dependência de sessão do banco ---
def get_session():
    with Session(fg.engine) as session:
        yield session


# --- Rotas CRUD para Product ---


# Listar todos os produtos (GET /products)
@fg.register_route(
    "/products",
    tags=["Products"],
    summary="Lista todos os produtos",
    response_model=list[Product],
)
def list_products(session: Session = Depends(get_session)):
    return Product.find_all(session)


# Obter um produto por ID (GET /products/{id})
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


# Criar um novo produto (POST /products)
@fg.register_route(
    "/products",
    methods=["POST"],
    tags=["Products"],
    summary="Cria um novo produto",
    response_model=Product,
    status_code=201,
)
def create_product(data: ProductCreate, session: Session = Depends(get_session)):
    # Cria uma instância de Product a partir dos dados
    new_product = Product(**data.dict())
    new_product.save(session)
    return new_product


# Atualizar parcialmente um produto (PATCH /products/{id})
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
    # Atualiza apenas os campos fornecidos
    update_data = data.dict(exclude_unset=True)
    product.update(session, **update_data)
    return product


# Deletar um produto (DELETE /products/{id})
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


# --- Inicialização do servidor ---
if __name__ == "__main__":
    fg.run()
