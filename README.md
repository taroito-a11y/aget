# セブン銀行 会話型UI（Assistants API連携）

このフォルダのHTMLモックを、OpenAI Assistants APIに接続して実際に会話できるようにした構成です。

## 1) セットアップ

```bash
cd /Users/taro.ito/Documents/Work/agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` の `OPENAI_API_KEY` を自分のキーに変更してください。  
`OPENAI_ASSISTANT_ID` は既定で `asst_CJffYUKAcUgyYHaDbroFkLEE` を利用します。

## 2) 起動

```bash
cd /Users/taro.ito/Documents/Work/agent
source .venv/bin/activate
python server.py
```

起動後、以下をブラウザで開いてください。

- `http://localhost:5001/`

## 3) 動作仕様

- `POST /api/chat/start` で新規 thread を作成
- `POST /api/chat/message` で thread にユーザーメッセージを追加し、assistant run を完了まで待って返信を返却
- UIの「新しい対話」で `thread_id` をリセットし、次回送信時に新しい thread を作成

## 4) 補足

- HTMLを `file://` で直接開く場合でも、フロントは `http://localhost:5001` に送信します。
- APIキーはフロントには埋め込まず、サーバー側のみで使用します。
