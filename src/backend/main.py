import os
from datetime import datetime
from typing import List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# 環境変数からDB接続情報を取得
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://dxadmin:dxpass123@db:5432/inventory_db"
)

app = FastAPI(
    title="物流倉庫 設備保守・部品在庫管理 API",
    description="Salesforce連携用 ローカル在庫管理バックエンドAPI (FastAPI + PostgreSQL)",
    version="1.0.0",
)


def get_db_connection():
    """PostgreSQLへの接続を取得するヘルパー関数"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {str(e)}"
        )


# ============================================================================
# Pydantic スキーマ定義 (リクエスト / レスポンス)
# ============================================================================

class PartInventoryResponse(BaseModel):
    part_id: str = Field(..., description="部品ID", examples=["PRT-001"])
    part_name: str = Field(..., description="部品名称")
    category: str = Field(..., description="カテゴリ")
    model_number: Optional[str] = Field(None, description="メーカー型番")
    unit: str = Field(..., description="管理単位")
    description: Optional[str] = Field(None, description="用途・備考")
    location_code: str = Field(..., description="保管棚番")
    quantity: int = Field(..., description="現在庫数")
    safety_stock: int = Field(..., description="安全在庫数")
    needs_reorder: bool = Field(..., description="発注アラート（現在庫 <= 安全在庫）")
    updated_at: datetime = Field(..., description="在庫最終更新日時")


class AllocateRequest(BaseModel):
    part_id: str = Field(..., description="引き当て対象の部品ID", examples=["PRT-002"])
    allocate_quantity: int = Field(
        ...,
        gt=0,
        description="引き当て数量（1以上の整数）",
        examples=[2]
    )
    work_order_id: Optional[str] = Field(
        None,
        description="Salesforce側の保守案件番号（任意）",
        examples=["WO-20261103-001"]
    )


class AllocateResponse(BaseModel):
    status: str = Field(..., examples=["success"])
    message: str = Field(..., examples=["在庫の引き当てが完了しました。"])
    part_id: str
    part_name: str
    allocated_quantity: int = Field(..., description="今回引き当てた数量")
    previous_quantity: int = Field(..., description="引き当て前の在庫数")
    remaining_quantity: int = Field(..., description="引き当て後の残在庫数")
    needs_reorder: bool = Field(..., description="安全在庫割れアラート")
    work_order_id: Optional[str] = None
    updated_at: datetime


# ============================================================================
# エンドポイント実装
# ============================================================================

@app.get("/health", tags=["System"])
def health_check():
    """コンテナのヘルスチェック用エンドポイント"""
    return {"status": "ok"}


@app.get(
    "/api/inventory",
    response_model=List[PartInventoryResponse],
    tags=["Inventory"],
    summary="全部品の在庫一覧取得"
)
@app.get(
    "/parts",
    response_model=List[PartInventoryResponse],
    tags=["Inventory"],
    summary="全部品の在庫一覧取得 (AWS連携用)"
)
@app.get(
    "/api/v1/parts",
    response_model=List[PartInventoryResponse],
    tags=["Inventory"],
    summary="全部品の在庫一覧取得 (AWS v1連携用)"
)
def list_inventory():
    """登録されているすべての部品マスタと現在庫数を一覧で返します。"""
    query = """
        SELECT
            p.part_id,
            p.part_name,
            p.category,
            p.model_number,
            p.unit,
            p.description,
            i.location_code,
            i.quantity,
            i.safety_stock,
            (i.quantity <= i.safety_stock) AS needs_reorder,
            i.updated_at
        FROM parts p
        INNER JOIN inventory i ON p.part_id = i.part_id
        ORDER BY p.part_id ASC;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


@app.get(
    "/api/inventory/{part_id}",
    response_model=PartInventoryResponse,
    tags=["Inventory"],
    summary="① 対象部品の在庫数と詳細を取得"
)
@app.get(
    "/parts/{part_id}",
    response_model=PartInventoryResponse,
    tags=["Inventory"],
    summary="① 対象部品の在庫数と詳細を取得 (AWS連携用)"
)
@app.get(
    "/api/v1/parts/{part_id}",
    response_model=PartInventoryResponse,
    tags=["Inventory"],
    summary="① 対象部品の在庫数と詳細を取得 (AWS v1連携用)"
)
def get_inventory_by_part_id(part_id: str):
    """指定された `part_id` の部品詳細情報と現在の在庫数を返します。"""
    query = """
        SELECT
            p.part_id,
            p.part_name,
            p.category,
            p.model_number,
            p.unit,
            p.description,
            i.location_code,
            i.quantity,
            i.safety_stock,
            (i.quantity <= i.safety_stock) AS needs_reorder,
            i.updated_at
        FROM parts p
        INNER JOIN inventory i ON p.part_id = i.part_id
        WHERE p.part_id = %s;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, (part_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error_code": "PART_NOT_FOUND",
                        "message": f"指定された部品ID '{part_id}' は存在しません。"
                    }
                )
            return row
    finally:
        conn.close()


@app.post(
    "/api/inventory/allocate",
    response_model=AllocateResponse,
    tags=["Inventory"],
    summary="② 対象部品の在庫引き当て（減算更新）処理"
)
@app.post(
    "/inventory/reserve",
    response_model=AllocateResponse,
    tags=["Inventory"],
    summary="② 対象部品の在庫引き当て処理 (AWS連携用)"
)
@app.post(
    "/api/v1/inventory/reserve",
    response_model=AllocateResponse,
    tags=["Inventory"],
    summary="② 対象部品の在庫引き当て処理 (AWS v1連携用)"
)
def allocate_inventory(req: AllocateRequest):
    """
    対象部品の在庫を引き当て（指定数をマイナスして更新）ます。
    トランザクション内で `SELECT ... FOR UPDATE` による行ロックを行い、
    複数作業員からの同時引き当てによる在庫不整合（レースコンディション）を防止します。
    """
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # 1. 対象部品の現在庫を行ロック付きで取得
                lock_query = """
                    SELECT
                        p.part_id,
                        p.part_name,
                        i.quantity,
                        i.safety_stock
                    FROM inventory i
                    INNER JOIN parts p ON p.part_id = i.part_id
                    WHERE i.part_id = %s
                    FOR UPDATE;
                """
                cur.execute(lock_query, (req.part_id,))
                current = cur.fetchone()

                if not current:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={
                            "error_code": "PART_NOT_FOUND",
                            "message": f"指定された部品ID '{req.part_id}' は存在しません。"
                        }
                    )

                prev_qty = current["quantity"]
                if prev_qty < req.allocate_quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "INSUFFICIENT_STOCK",
                            "message": "在庫数が不足しているため引き当てできません。",
                            "part_id": req.part_id,
                            "requested_quantity": req.allocate_quantity,
                            "current_quantity": prev_qty
                        }
                    )

                # 2. 在庫数を減算して更新
                update_query = """
                    UPDATE inventory
                    SET quantity = quantity - %s,
                        updated_at = NOW()
                    WHERE part_id = %s
                    RETURNING quantity, safety_stock, updated_at;
                """
                cur.execute(update_query, (req.allocate_quantity, req.part_id))
                updated = cur.fetchone()

                return {
                    "status": "success",
                    "message": "在庫の引き当てが完了しました。",
                    "part_id": req.part_id,
                    "part_name": current["part_name"],
                    "allocated_quantity": req.allocate_quantity,
                    "previous_quantity": prev_qty,
                    "remaining_quantity": updated["quantity"],
                    "needs_reorder": updated["quantity"] <= updated["safety_stock"],
                    "work_order_id": req.work_order_id,
                    "updated_at": updated["updated_at"],
                }
    finally:
        conn.close()

