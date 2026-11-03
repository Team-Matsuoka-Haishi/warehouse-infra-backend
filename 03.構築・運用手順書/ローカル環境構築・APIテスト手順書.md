# ローカル環境構築・APIテスト手順書（WSL2 + Podman）

本ドキュメントは、WSL2上のPodman環境で「PostgreSQLデータベース」および「FastAPIバックエンドサーバー」を起動し、`curl` コマンドで在庫照会・引き当てAPIの動作確認を行う手順書です。

---

## 1. 構成ファイル一覧

プロジェクト内の以下のパスに各実装ファイルを配置しています。

* [`deploy/podman-compose.yml`](../deploy/podman-compose.yml) : コンテナオーケストレーション定義
* [`src/db/init.sql`](../src/db/init.sql) : DBテーブル作成（`parts`, `inventory`）および初期ダミーデータ6件投入スクリプト
* [`src/backend/main.py`](../src/backend/main.py) : FastAPI バックエンドAPI実装（AWSプロキシ用エイリアスルーティング対応）
* [`src/backend/Dockerfile`](../src/backend/Dockerfile) : APIコンテナビルド定義
* [`src/backend/requirements.txt`](../src/backend/requirements.txt) : Pythonパッケージ定義

---

## 2. コンテナのビルドおよび起動手順

### Step 1: `deploy` ディレクトリへ移動
WSL2のターミナルを開き、プロジェクトの `deploy` フォルダへ移動します。

```bash
cd "/mnt/g/マイドライブ/個人開発/ハイブリッドDX基盤構築プロジェクト/deploy"
```

### Step 2: コンテナのビルドとバックグラウンド起動
`podman-compose` コマンドでイメージのビルドとコンテナ起動を一括実行します。  
（`.env` ファイルを作成していなくても、デフォルト値 `dxadmin` / `dxpass123` で即座に起動できるよう設定済みです）

```bash
podman-compose up -d --build
```

> **💡 コード変更時の反映について**:
> `podman-compose.yml` にて `../src/backend/main.py:/app/main.py:ro` をボリュームマウントしているため、`main.py` を修正した際はイメージの再ビルドを行わなくても、以下のコマンドでコンテナを再作成するだけで最新コードが反映されます。
> ```bash
> podman rm -f dx-fastapi && podman-compose up -d api
> ```

### Step 3: 起動状態と初期データの確認
コンテナが2つ（`dx-postgres`, `dx-fastapi`）正常に稼働していることを確認します。

```bash
podman ps
```

DBコンテナ内のテーブルとダミーデータ（6件）が自動投入されたか確認する場合は、以下のコマンドを実行します。

```bash
podman exec -it dx-postgres psql -U dxadmin -d inventory_db -c "SELECT p.part_id, p.part_name, i.location_code, i.quantity FROM parts p JOIN inventory i ON p.part_id = i.part_id;"
```

---

## 3. APIエンドポイント一覧とテスト手順（`curl` コマンド）

APIサーバーは `http://localhost:8000` で待ち受けています。  
ローカルパスおよびAWS連携用エイリアスパスのどちらでも同じ処理が呼び出せます。

| 機能 | メソッド | ローカルパス | AWS連携用エイリアスパス |
| :--- | :---: | :--- | :--- |
| **全部品一覧取得** | `GET` | `/api/inventory` | `/parts`<br/>`/api/v1/parts` |
| **個別部品照会** | `GET` | `/api/inventory/{part_id}` | `/parts/{part_id}`<br/>`/api/v1/parts/{part_id}` |
| **在庫引き当て** | `POST` | `/api/inventory/allocate` | `/inventory/reserve`<br/>`/api/v1/inventory/reserve` |
| **ヘルスチェック** | `GET` | `/health` | - |

---

### テスト①：全部品の在庫一覧を取得 (`GET /parts` または `GET /api/inventory`)

```bash
curl -X GET "http://localhost:8000/parts"
```

---

### テスト②：対象部品の在庫数と詳細を取得 (`GET /api/v1/parts/{part_id}` または `GET /api/inventory/{part_id}`)

#### 1) 正常系テスト（光電センサー `PRT-002` の照会）
```bash
curl -X GET "http://localhost:8000/api/v1/parts/PRT-002"
```

**期待されるレスポンス例 (`200 OK`)**:
```json
{
  "part_id": "PRT-002",
  "part_name": "光電センサー (反射型・長距離)",
  "category": "電気・センサー",
  "model_number": "E3Z-D82",
  "unit": "個",
  "description": "パレット通過検知用センサー（第1〜第3ライン共通）",
  "location_code": "B-02-03",
  "quantity": 12,
  "safety_stock": 5,
  "needs_reorder": false,
  "updated_at": "2026-11-03T10:20:00.123456+09:00"
}
```

#### 2) 異常系テスト（存在しない部品ID `PRT-999` の照会）
```bash
curl -i -X GET "http://localhost:8000/api/v1/parts/PRT-999"
```

**期待されるレスポンス例 (`404 Not Found`)**:
```json
{
  "detail": {
    "error_code": "PART_NOT_FOUND",
    "message": "指定された部品ID 'PRT-999' は存在しません。"
  }
}
```

---

### テスト③：対象部品の在庫を引き当てる (`POST /api/v1/inventory/reserve` または `POST /api/inventory/allocate`)

#### 1) 正常系テスト（光電センサー `PRT-002` を `2個` 引き当て）
初期在庫 `12個` から `2個` を引き当て、残在庫が `10個` になることを確認します。

```bash
curl -X POST "http://localhost:8000/api/v1/inventory/reserve" \
  -H "Content-Type: application/json" \
  -d '{
    "part_id": "PRT-002",
    "allocate_quantity": 2,
    "work_order_id": "WO-20261103-001"
  }'
```

**期待されるレスポンス例 (`200 OK`)**:
```json
{
  "status": "success",
  "message": "在庫の引き当てが完了しました。",
  "part_id": "PRT-002",
  "part_name": "光電センサー (反射型・長距離)",
  "allocated_quantity": 2,
  "previous_quantity": 12,
  "remaining_quantity": 10,
  "needs_reorder": false,
  "work_order_id": "WO-20261103-001",
  "updated_at": "2026-11-03T10:25:15.654321+09:00"
}
```

#### 2) 異常系テスト（在庫不足エラーの確認）
現在庫（`10個`）を超える `99個` の引き当てを要求し、ロールバックとエラー返却が行われることを確認します。

```bash
curl -i -X POST "http://localhost:8000/api/v1/inventory/reserve" \
  -H "Content-Type: application/json" \
  -d '{
    "part_id": "PRT-002",
    "allocate_quantity": 99
  }'
```

**期待されるレスポンス例 (`400 Bad Request`)**:
```json
{
  "detail": {
    "error_code": "INSUFFICIENT_STOCK",
    "message": "在庫数が不足しているため引き当てできません。",
    "part_id": "PRT-002",
    "requested_quantity": 99,
    "current_quantity": 10
  }
}
```

---

## 4. コンテナの停止・データ初期化コマンド

* **コンテナの停止**:
  ```bash
  podman-compose down
  ```
* **DBのデータボリュームも含めて完全に初期状態（`init.sql` 再実行）に戻す場合**:
  ```bash
  podman-compose down -v
  podman-compose up -d --build
  ```
