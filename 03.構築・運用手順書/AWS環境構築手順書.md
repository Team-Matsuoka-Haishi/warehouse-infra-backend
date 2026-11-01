# AWS環境構築手順書

本ドキュメントは、物流倉庫の設備保守・部品在庫管理DX基盤における **AWS環境（Amazon API Gateway および AWS Lambda）** の構築・設定手順書です。  
AWSマネジメントコンソールのGUI操作を中心に、迷わず正確に設定できるようステップバイステップで記述しています。

---

## 1. 概要と事前準備

### 1.1. 設定対象リソース一覧
* **リージョン**: アジアパシフィック (東京) `ap-northeast-1`
* **IAMロール**: `dx-inventory-lambda-exec-role`
* **AWS Lambda**: `dx-inventory-proxy-fn` (Python 3.12 / ARM64)
* **Amazon API Gateway**: `dx-inventory-api` (REST API / ステージ `v1`)
* **APIキー & 使用量プラン**: `dx-inventory-plan` / `dx-sf-client-key`

### 1.2. 準備するもの
* AWSマネジメントコンソールへのログイン権限（管理者またはIAM/Lambda/APIGatewayの操作権限）
* 将来的に設定するCloudflare Tunnelの公開ホスト名（※後から環境変数で変更可能です）

---

## 2. Step 1: IAMロールの作成

Lambda関数がCloudWatch Logsにログを出力するための最小権限IAMロールを作成します。

1. **IAMコンソールを開く**:
   * AWSマネジメントコンソール上部の検索バーで「IAM」を検索し、IAMダッシュボードに移動します。
2. **ロールの作成開始**:
   * 左側メニューの「ロール」をクリックし、右上の「ロールを作成」ボタンを押します。
3. **信頼されたエンティティタイプ**:
   * 「AWSのサービス」を選択。
   * ユースケースとして「Lambda」を選択し、「次へ」をクリックします。
4. **許可ポリシーの追加**:
   * ポリシー一覧の検索窓に `AWSLambdaBasicExecutionRole` と入力します。
   * チェックボックスにチェックを入れ、「次へ」をクリックします。
5. **名前と確認**:
   * ロール名: `dx-inventory-lambda-exec-role`
   * 説明: `Role for inventory DX Lambda proxy function with logging permissions`
   * 「ロールを作成」ボタンをクリックして完了します。

---

## 3. Step 2: AWS Lambda関数の作成と設定

Salesforceからのリクエストを受け取り、Cloudflare Tunnel経由でローカルAPIへプロキシ転送するLambda関数を作成します。

### 3.1. 関数の作成
1. **Lambdaコンソールを開く**:
   * AWS検索バーで「Lambda」を検索し、Lambdaダッシュボードに移動します。
2. **関数の作成開始**:
   * 「関数の作成」ボタンをクリックします。
3. **基本設定**:
   * 「一から作成」を選択。
   * **関数名**: `dx-inventory-proxy-fn`
   * **ランタイム**: `Python 3.12`
   * **アーキテクチャ**: `arm64` （コスト・パフォーマンスに優れるGravitonを選択）
4. **アクセス権限**:
   * 「デフォルトの実行ロールの変更」を展開。
   * 「既存のロールを使用する」を選択。
   * 既存のロールから先ほど作成した `dx-inventory-lambda-exec-role` を選択。
5. 「関数の作成」をクリックします。

### 3.2. ソースコードのデプロイ
1. 作成した関数の「コード」タブを選択します。
2. `lambda_function.py` をダブルクリックしてエディタを開き、既存のコードを全削除して以下のコードを貼り付けます。

```python
import json
import os
import urllib.request
import urllib.error
import urllib.parse

TUNNEL_BASE_URL = os.environ.get("TUNNEL_BASE_URL", "https://placeholder.example.com").rstrip("/")
CF_CLIENT_ID = os.environ.get("CF_ACCESS_CLIENT_ID", "")
CF_CLIENT_SECRET = os.environ.get("CF_ACCESS_CLIENT_SECRET", "")
INTERNAL_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "")

def lambda_handler(event, context):
    print(f"Incoming event: path={event.get('path')}, method={event.get('httpMethod')}")
    
    http_method = event.get("httpMethod", "GET")
    resource_path = event.get("path", "")
    query_params = event.get("queryStringParameters") or {}
    body = event.get("body")

    # API Gatewayのパスプレフィックスを除去してFastAPIの /api/v1/... へ転送
    target_url = f"{TUNNEL_BASE_URL}/api/v1{resource_path}"
    if query_params:
        target_url += "?" + urllib.parse.urlencode(query_params)

    headers = {
        "Content-Type": "application/json",
        "CF-Access-Client-Id": CF_CLIENT_ID,
        "CF-Access-Client-Secret": CF_CLIENT_SECRET,
        "X-Internal-Token": INTERNAL_TOKEN,
        "User-Agent": "AWS-Lambda-Inventory-Proxy/1.0"
    }

    req_data = body.encode("utf-8") if body else None
    req = urllib.request.Request(target_url, data=req_data, headers=headers, method=http_method)

    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            res_body = res.read().decode("utf-8")
            return {
                "statusCode": res.status,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": res_body
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"HTTPError from upstream: {e.code} - {err_body}")
        return {
            "statusCode": e.code,
            "headers": {"Content-Type": "application/json"},
            "body": err_body or json.dumps({"error": "Upstream API Error"})
        }
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 502,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Bad Gateway (Tunnel unreachable)", "detail": str(e)})
        }
```

3. エディタ上部の **「Deploy」** ボタンを押して保存・反映します。

### 3.3. 一般設定（タイムアウト変更）
1. 「設定」タブ > 「一般設定」 > 「編集」をクリックします。
2. **タイムアウト**: デフォルトの3秒から **`10秒`** に変更します。
3. **メモリ**: `128 MB` のままで問題ありません。
4. 「保存」をクリックします。

### 3.4. 環境変数の設定
1. 「設定」タブ > 「環境変数」 > 「編集」をクリックします。
2. 以下の4つのキーと値を入力します（未定の値はプレースホルダーで可）。

| キー | 値（例） | 説明 |
| :--- | :--- | :--- |
| `TUNNEL_BASE_URL` | `https://api-inventory.yourdomain.com` | Cloudflare Tunnelの公開ホスト名 |
| `CF_ACCESS_CLIENT_ID` | `xxxxxxxx.access` | Cloudflare Access Service Token ID |
| `CF_ACCESS_CLIENT_SECRET` | `yyyyyyyyyyyyyyyy` | Cloudflare Access Service Token Secret |
| `INTERNAL_API_TOKEN` | `dx-warehouse-secure-token-2026` | FastAPI側と共有する内部認証トークン |

3. 「保存」をクリックします。

---

## 4. Step 3: Amazon API Gatewayの作成と設定

REST APIエンドポイントを構築し、APIキー認証を有効化します。

### 4.1. REST APIの新規作成
1. **API Gatewayコンソールを開く**:
   * AWS検索バーで「API Gateway」を検索して移動します。
2. **APIの作成**:
   * 「REST API」（※「REST API プライベート」ではない方）の「構築」ボタンをクリックします。
3. **プロトコルと基本設定**:
   * プロトコル: `REST` を選択
   * 新しいAPIの作成: `新しいAPI` を選択
   * **API名**: `dx-inventory-api`
   * **説明**: `物流倉庫 設備保守部品 在庫管理API`
   * **エンドポイントタイプ**: `リージョン`
4. 「APIの作成」をクリックします。

### 4.2. リソースとメソッドの作成
設計書に基づき、以下の4つのエンドポイントを作成します。

#### ① `/parts` リソース & `GET` メソッド
1. 「リソース」一覧で `/`（ルート）を選択した状態で、「リソースを作成」をクリック。
   * リソースパス: `/`
   * リソース名: `parts`
   * 「リソースを作成」をクリック。
2. 作成された `/parts` を選択した状態で、「メソッドを作成」をクリック。
   * メソッドタイプ: `GET`
   * 統合タイプ: `Lambda 関数`
   * **Lambda プロキシ統合**: **ON（有効）** ※必須
   * Lambda リージョン: `ap-northeast-1`
   * Lambda 関数: `dx-inventory-proxy-fn`
   * 「メソッドを作成」をクリック（Lambdaの呼び出し権限付与ダイアログが出た場合は「OK」）。
3. 作成された `GET` メソッドを選択し、「メソッドリクエストの編集」をクリック。
   * **APIキーが必要**: **`true`** に設定し、「保存」。

#### ② `/parts/{part_code}` リソース & `GET` メソッド
1. `/parts` を選択した状態で「リソースを作成」。
   * リソース名: `{part_code}`
   * リソースパス: `{part_code}`
   * 「リソースを作成」をクリック。
2. `/{part_code}` を選択した状態で「メソッドを作成」。
   * メソッドタイプ: `GET`
   * 統合タイプ: `Lambda 関数`
   * **Lambda プロキシ統合**: **ON（有効）**
   * Lambda 関数: `dx-inventory-proxy-fn`
   * 「メソッドを作成」をクリック。
3. `GET` メソッドの「メソッドリクエストの編集」で **APIキーが必要: `true`** に設定して保存。

#### ③ `/inventory/reserve` リソース & `POST` メソッド
1. `/`（ルート）を選択して「リソースを作成」。
   * リソース名: `inventory`
   * 「リソースを作成」。
2. `/inventory` を選択して「リソースを作成」。
   * リソース名: `reserve`
   * 「リソースを作成」。
3. `/inventory/reserve` を選択して「メソッドを作成」。
   * メソッドタイプ: `POST`
   * 統合タイプ: `Lambda 関数`
   * **Lambda プロキシ統合**: **ON（有効）**
   * Lambda 関数: `dx-inventory-proxy-fn`
   * 「メソッドを作成」。
4. `POST` メソッドの「メソッドリクエストの編集」で **APIキーが必要: `true`** に設定して保存。

#### ④ `/inventory/consume` リソース & `POST` メソッド
1. `/inventory` を選択して「リソースを作成」。
   * リソース名: `consume`
   * 「リソースを作成」。
2. `/inventory/consume` を選択して「メソッドを作成」。
   * メソッドタイプ: `POST`
   * 統合タイプ: `Lambda 関数`
   * **Lambda プロキシ統合**: **ON（有効）**
   * Lambda 関数: `dx-inventory-proxy-fn`
   * 「メソッドを作成」。
3. `POST` メソッドの「メソッドリクエストの編集」で **APIキーが必要: `true`** に設定して保存。

### 4.3. APIのデプロイ
1. 右上の青いボタン「APIをデプロイ」をクリックします。
2. **ステージ**: `新しいステージ` を選択。
3. **ステージ名**: `v1`
4. **説明**: `本番用ステージ v1`
5. 「デプロイ」をクリックします。
6. 画面上部に表示される **「URL の呼び出し」**（例: `https://xxxxxx.execute-api.ap-northeast-1.amazonaws.com/v1`）をメモしておきます。

---

## 5. Step 4: APIキーと使用量プラン（Usage Plan）の作成

不正リクエストによる課金爆発防止とSalesforce向け認証キーを発行します。

### 5.1. 使用量プランの作成
1. API Gatewayの左メニューから「使用量プラン」をクリックします。
2. 「使用量プランを作成」をクリックします。
   * **名前**: `dx-inventory-basic-plan`
   * **レート**: `10` リクエスト/秒
   * **バースト**: `20`
   * **クォータを有効化**: チェックを入れる
   * **クォータ**: `10000` リクエスト / 月
3. 「次へ」をクリックします。
4. **関連付けられた API ステージ**:
   * 「API ステージの追加」をクリック。
   * API: `dx-inventory-api`
   * ステージ: `v1`
   * チェックマークアイコンを押して確定し、「次へ」。

### 5.2. APIキーの作成と紐付け
1. 続く画面で「API キーを作成して使用量プランに追加」をクリックします。
   * **名前**: `dx-salesforce-client-key`
   * **自動生成**: 選択
   * 「API キーを保存」をクリック。
2. 「完了」をクリックします。
3. 左メニューの「API キー」を開き、作成された `dx-salesforce-client-key` をクリックします。
4. 「API キー」欄の **「表示」** をクリックし、表示された文字列（例: `abc123xyz...`）を控えます（※SalesforceのNamed Credentialsに登録する値です）。

---

## 6. Step 5: 疎通テスト手順

### 6.1. APIキーなしでの遮断テスト
PowerShellまたはターミナルから、APIキーを付与せずにリクエストを送信します。

```powershell
curl -X GET "https://<あなたのAPI-ID>.execute-api.ap-northeast-1.amazonaws.com/v1/parts"
```

* **期待されるレスポンス**:
  ```json
  {"message":"Forbidden"}
  ```
  （HTTP 403 Forbiddenとなり、APIキーがないリクエストが正常に弾かれていることを確認）

### 6.2. 正しいAPIキーを付与した疎通テスト
ヘッダー `x-api-key` を付与してリクエストを送信します。

```powershell
curl -X GET "https://<あなたのAPI-ID>.execute-api.ap-northeast-1.amazonaws.com/v1/parts" `
  -H "x-api-key: <控えたAPIキー文字列>"
```

* **期待されるレスポンス**:
  * Cloudflare/ローカルAPIが未起動の場合: `502 Bad Gateway`（Lambdaまでは正常に疎通し、接続先が見つからないエラーが返るためAWS側の設定としては正常です）
  * ローカルAPI起動後の場合: `200 OK` と部品一覧JSON

### 6.3. CloudWatch Logsの確認
1. AWSマネジメントコンソールで「CloudWatch」を開きます。
2. 左メニュー「ログ」>「ロググループ」を開きます。
3. `/aws/lambda/dx-inventory-proxy-fn` というロググループが存在し、実行ログ（`Incoming event: path=/parts, method=GET` など）が出力されていることを確認します。

---

## 7. 付録: Salesforce連携用 設定パラメータ控えシート

AWS側の設定完了後、Salesforce担当者（またはご自身でのSalesforce構築時）に引き渡すパラメータ一覧です。

| 項目名 | 設定値（実際の値に書き換えて保管） | 備考 |
| :--- | :--- | :--- |
| **API ベースURL** | `https://<API-ID>.execute-api.ap-northeast-1.amazonaws.com/v1` | Salesforce Named CredentialsのURL |
| **API キー (Header)** | `x-api-key: xxxxxxxxxxxxxxxxxxxxxxxx` | Salesforce Named Credentialsの認証ヘッダ |
| **エンドポイント① 在庫一覧** | `GET /parts` | クエリパラメータ: `keyword`, `category` |
| **エンドポイント② 部品詳細** | `GET /parts/{part_code}` | パスパラメータ: 部品コード |
| **エンドポイント③ 在庫引当** | `POST /inventory/reserve` | JSONボディ: `idempotency_key`, `quantity` 等 |
| **エンドポイント④ 消費確定** | `POST /inventory/consume` | JSONボディ: `idempotency_key`, `quantity` 等 |

