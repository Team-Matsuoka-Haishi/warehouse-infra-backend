import json
import os
import urllib.request
import urllib.error
import urllib.parse

# 環境変数から設定値を取得
TUNNEL_BASE_URL = os.environ.get("TUNNEL_BASE_URL", "https://placeholder.example.com").rstrip("/")
CF_CLIENT_ID = os.environ.get("CF_ACCESS_CLIENT_ID", "")
CF_CLIENT_SECRET = os.environ.get("CF_ACCESS_CLIENT_SECRET", "")
INTERNAL_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "")

def lambda_handler(event, context):
    """
    SalesforceからのAPI Gateway経由リクエストを受け取り、
    Cloudflare AccessのService Tokenを付与してCloudflare Tunnel経由で
    ローカルFastAPIへ転送するリバースプロキシハンドラー
    """
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

