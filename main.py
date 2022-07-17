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

import random

load_dotenv()
cred = credentials.Certificate(json.loads(os.getenv("FIREBASE_CRED")))
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
    print(event.source)
    if(event.message.text[:3] == "割り勘"):
        total_price = re.search(r'\d+',event.message.text)
        if(total_price is not None):
            init_data(event,total_price.group())
        else:
            line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="入力方式が間違っているよ！\n割り勘<金額>円の形でもう一度送信してね！")
        )

            
    if event.message.text == "test":
        print(event)
    """line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=event.message.text))"""

def init_data(event,total_price):
    doc_ref = firestore.collection("payments").document()
    doc_ref.set({
        "group_id":event.source.group_id,
        "total_price":int(total_price),
        "users":{}
    })
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="https://liff.line.me/1657307954-mJEJ8lW4/?sessionId="+doc_ref.id+"&totalPrice="+total_price)
    )

@app.route("/payment",methods=['POST'])
def post_payment():
    print(request.json)
    doc_ref = firestore.collection('payments').document(request.json["sessionId"])  #扱うドキュメントを指定する
    users_ref = doc_ref.get().to_dict() #ここで取得する
    users_ref["users"][request.json["userId"]] = request.json["userData"]  #ここでkeyに存在しないuserIdを指定した場合に新しくuserIdをkeyに持つ連想配列を追加する。既にuserIdが存在した場合上書きする
    users_ref["users"][request.json["userId"]]["max_offer"] = True
    users_ref["users"][request.json["userId"]]["min_offer"] = True
    for userId in users_ref["users"]:
        if(users_ref["users"][userId]["max_offer"] == True):
            if(users_ref["users"][userId]["payment_offer_price"] < users_ref["users"][request.json["userId"]]["payment_offer_price"]):
                users_ref["users"][userId]["max_offer"] = False
            elif(users_ref["users"][userId]["payment_offer_price"] != users_ref["users"][request.json["userId"]]["payment_offer_price"]):
                users_ref["users"][request.json["userId"]]["max_offer"] = False
        if(users_ref["users"][userId]["min_offer"] == True):
            if(users_ref["users"][userId]["payment_offer_price"] > users_ref["users"][request.json["userId"]]["payment_offer_price"]):
                users_ref["users"][userId]["min_offer"] = False
            elif(users_ref["users"][userId]["payment_offer_price"] != users_ref["users"][request.json["userId"]]["payment_offer_price"]):
                users_ref["users"][request.json["userId"]]["min_offer"] = False
    doc_ref.update({"users":users_ref["users"]})   #firestoreのusersを上書きする
    members_count = line_bot_api.get_group_members_count(users_ref["group_id"])
    users_ref = doc_ref.get().to_dict()
    if(members_count == len(users_ref["users"])):
        #print(members_count)
        total_offer_price = 0
        for userId in users_ref["users"]:
            total_offer_price += users_ref["users"][userId]["payment_offer_price"]
        rich_members = []
        poor_members = []
        print(users_ref["total_price"])
        print(type(users_ref["total_price"]))
        if(total_offer_price >= users_ref["total_price"]):
            #print(total_offer_price)
            paymented_price = 0
            for userId in users_ref["users"]:
                users_ref["users"][userId]["payment_price"] = users_ref["total_price"] * (users_ref["users"][userId]["payment_offer_price"] / total_offer_price) // max(pow(10,len(str(users_ref["total_price"]))-3),1)*max(pow(10,len(str(users_ref["total_price"]))-3),1)
                paymented_price += users_ref["users"][userId]["payment_price"]
                if users_ref["users"][userId]["max_offer"] == True:
                    rich_members.append(userId)
                if users_ref["users"][userId]["min_offer"] == True:
                    poor_members.append(userId)
            for rich_member in rich_members:
                users_ref["users"][rich_member]["payment_price"] += users_ref["total_price"] % max(pow(10,len(str(users_ref["total_price"]))-3),1) // len(rich_members)
                paymented_price += users_ref["total_price"] % max(pow(10,len(str(users_ref["total_price"]))-3),1) // len(rich_members)
            #print(paymented_price)
            users_ref["users"][random.choice(rich_members)]["payment_price"] += users_ref["total_price"] - paymented_price
            users_ref["users"]["rich_members"] = rich_members
            users_ref["users"]["poor_members"] = poor_members
            doc_ref.update({"users":users_ref["users"]})
            #print(total_offer_price)

            if len(users_ref["users"]) == len(rich_members):
                white_message = "みんな同じ金額を支払いました！"
                line_bot_api.push_message(users_ref["group_id"], TextSendMessage(text=white_message))
            else:
                black_message = "一番多く払った人\n"
                for rich_member in rich_members:
                    black_message += "  " + users_ref["users"][rich_member]["user_name"] + " : " + str(int(users_ref["users"][rich_member]["payment_price"])) + "円\n"
                black_message += "一番払わなかった人\n"
                for poor_member in poor_members:
                    black_message += "  " + users_ref["users"][poor_member]["user_name"] + " : " + str(int(users_ref["users"][poor_member]["payment_price"])) + "円\n"
                line_bot_api.push_message(users_ref["group_id"], TextSendMessage(text=black_message))
            #line_bot_api.push_message(users_ref["group_id"], TextSendMessage(users_ref["users"][userId]["min_offer"]))
                #print(users_ref)
            line_bot_api.push_message(users_ref["group_id"],TextSendMessage(text="https://liff.line.me/1657307954-mJEJ8lW4/result/?sessionId="+doc_ref.id))
        else:
            #print(total_offer_price)
            doc_ref.update({"users":{}}) 
            resend_message = "全員の合計が支払い金額に届かなかったよ！再度入力し直してね！\nヒント：少し大きめの額にして太っ腹なところを見せつけよう！\n\nhttps://liff.line.me/1657307954-mJEJ8lW4/?sessionId="+doc_ref.id+"&totalPrice="+str(users_ref["total_price"])
            line_bot_api.push_message(users_ref["group_id"], TextSendMessage(text=resend_message))
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
    payments_ref = firestore.collection("payments").document("2QY4a5P14XDkao7EQ0C6")
    payments_ref.update({"users":{"userId2":{"userName":"userName",'paymentOfferPrice':5000}}})
    #print(docs.to_dict())
    return "su",200

if __name__ == "__main__":
#    app.run()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port,debug=True)
