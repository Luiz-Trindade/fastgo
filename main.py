from src.fastgo.core import FastGo
from src.fastgo.models import FastModel, Field


class Product(FastModel, table=True):
    name: str = Field(nullable=False, description="Nome do produto")
    price: float = Field(nullable=False, description="Preço do produto")
    stock: int = Field(default=0, nullable=False, description="Quantidade em estoque")


fg = FastGo(database_url="sqlite:///fastgo.db", database_models=[Product])
fg.register_model(Product, tags=["Products"])

if __name__ == "__main__":
    fg.run()
