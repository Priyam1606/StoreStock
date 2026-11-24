from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from app.db import init_db
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.products import router as products_router
from app.routers.stock import router as stock_router
from app.routers.sales import router as sales_router
from app.routers.customers import router as customers_router
from app.routers.suppliers import router as suppliers_router
from app.routers.purchase_orders import router as purchase_orders_router
from app.routers.reports import router as reports_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


app = FastAPI(title="StoreStock", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    message = errors[0].get("msg", "Validation error") if errors else "Validation error"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": message},
    )


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(products_router, prefix="/products", tags=["products"])
app.include_router(stock_router, prefix="/stock", tags=["stock"])
app.include_router(sales_router, prefix="/sales", tags=["sales"])
app.include_router(customers_router, prefix="/customers", tags=["customers"])
app.include_router(suppliers_router, prefix="/suppliers", tags=["suppliers"])
app.include_router(purchase_orders_router, prefix="/purchase-orders", tags=["purchase-orders"])
app.include_router(reports_router, prefix="/reports", tags=["reports"])

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
@app.get("/app", include_in_schema=False)
@app.get("/app/", include_in_schema=False)
def serve_app() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")

