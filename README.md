# 物流倉庫 設備保守・部品在庫管理DX プロジェクト

物流倉庫における設備保守業務および部品の在庫管理業務をデジタル化し、保守作業の効率化と在庫の正確な把握を実現するハイブリッドDX基盤です。

---

## 📁 ディレクトリ構成

本プロジェクトは、ドキュメント管理、クラウド設定、コンテナ実行環境、各レイヤーの実装コードを分離したエンタープライズ標準の構成を採用しています。

```
ハイブリッドDX基盤構築プロジェクト/
├── 00.管理/                      # WBS、議事録、要件整理資料
├── 01.基本設計書/                # アーキテクチャ構成図、通信フロー、基本方針
│   └── インフラ・バックエンド基本設計書.md
├── 02.詳細設計書/                # API仕様、DB設計、コンテナ定義詳細
│   └── インフラ・バックエンド詳細設計書.md
├── 03.構築・運用手順書/          # クラウド/ミドルウェアのセットアップ手順書
│   └── AWS環境構築手順書.md
├── 99.docs/                      # その他参考資料、プレゼン・フライヤー等
├── deploy/                       # コンテナオーケストレーション・デプロイ設定
│   ├── podman-compose.yml        # Podman (WSL2) 起動定義
│   └── .env.example              # 環境変数テンプレート
├── src/                          # ソースコード資材ルート
│   ├── backend/                  # FastAPI バックエンドAPIサーバー
│   ├── db/                       # PostgreSQL 初期化スクリプト (init.sql)
│   ├── aws/                      # AWS Lambda プロキシ関数コード
│   └── salesforce/               # Salesforce (Apex / LWC / Flow) 資材
├── .gitignore                    # Git除外定義
└── README.md                     # 本ドキュメント
```

---

## 🛠 技術スタック概要

* **フロントエンド / CRM**: Salesforce Developer Edition (Lightning Web Components, 画面フロー)
* **APIゲートウェイ**: Amazon API Gateway (REST API / APIキー認証)
* **リバースプロキシ**: AWS Lambda (Python 3.12 / ARM64 Graviton)
* **セキュアトンネリング**: Cloudflare Tunnels (`cloudflared`) + Cloudflare Access
* **コンテナオーケストレーション**: WSL2 + Podman (`podman-compose`)
* **バックエンドAPI**: FastAPI (Python 3.12, Pydantic, SQLAlchemy)
* **データベース**: PostgreSQL 16 (行ロック制御, べき等性担保トランザクション)

---

## 🚀 クイックスタートガイド

1. **ドキュメントの確認**:
   * [インフラ・バックエンド基本設計書.md](file:///g:/マイドライブ/個人開発/ハイブリッドDX基盤構築プロジェクト/01.基本設計書/インフラ・バックエンド基本設計書.md)
   * [インフラ・バックエンド詳細設計書.md](file:///g:/マイドライブ/個人開発/ハイブリッドDX基盤構築プロジェクト/02.詳細設計書/インフラ・バックエンド詳細設計書.md)
2. **クラウド環境の準備**:
   * [AWS環境構築手順書.md](file:///g:/マイドライブ/個人開発/ハイブリッドDX基盤構築プロジェクト/03.構築・運用手順書/AWS環境構築手順書.md) に従ってAPI GatewayとLambdaを設定。
3. **ローカルコンテナの起動**:
   * `deploy/.env.example` をコピーして `deploy/.env` を作成し、必要なトークン・パスワードを設定。
   * Podman Composeでサービスを一括起動。

