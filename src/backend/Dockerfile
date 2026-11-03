# Podmanでの対話プロンプト回避のため完全修飾イメージ名(docker.io/...)を指定
FROM docker.io/library/python:3.12-slim

# 作業ディレクトリの設定
WORKDIR /app

# Pythonの環境変数設定（バッファリング無効化・.pyc生成防止）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 依存パッケージのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY main.py .

# ポート8000を公開
EXPOSE 8000

# Uvicornサーバーの起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

