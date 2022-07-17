from email import message
from flask import Flask, request, abort
from dotenv import load_dotenv
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
import os
import json

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

import secrets

import re

load_dotenv()
cred = credentials.Certificate("firebase/cred.json")
firebase_admin.initialize_app(cred)

firestore = firestore.client()



app = Flask(__name__)

#環境変数取得
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]

line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)

@app.route("/",methods=["GET"])
def index():
    return "Hello World!"

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print(event.message.text)
    if(event.message.text[:3] == "割り勘"):
        total_price = re.search(r'\d+',event.message.text)
        if(total_price is not None):
            init_data(event,total_price.group())
        else:
            line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="入力方式が間違っています！\n割り勘<金額>円の形で再送信してください！")
        )

            
    if event.message.text == "test":
        print(event)
    """line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=event.message.text))"""

def init_data(event,total_price):
    doc_ref = firestore.collection("payments").document()
    doc_ref.set({
        "group_id":event.source.groupId,
        "total_price":total_price
    })
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="https://liff.line.me/1657307954-mJEJ8lW4/?sessionId="+doc_ref.id)
    )

@app.route("/payment",methods=['POST'])
def post_payment():
    print(request.json)
    return "success",200

@app.route("/init_data/<group_id>",methods=['GET'])
def fetch_user_data(group_id):
    print(group_id)
    member_ids_res = line_bot_api.get_group_member_profile(group_id,"Ue3c84d1413d2c71275f863f3c03a454a")
    print(member_ids_res.display_name)
    return "s",200 

@app.route("/test",methods=["GET"])
def create_doc():
    doc_ref = firestore.collection("payments").document()
    doc_ref.set({
        "foo": secrets.token_hex(32)
    })
    print(doc_ref.id)
    return "doc_ref.key",200

@app.route("/test2",methods=["GET"])
def read_doc():
    payments_ref = firestore.collection("payments").add()
    doc = payments_ref.get()
    print(doc.to_dict())
    #print(docs.to_dict())
    return "su",200

if __name__ == "__main__":
#    app.run()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port,debug=True)
