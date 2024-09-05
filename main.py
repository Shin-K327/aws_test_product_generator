import base64
import sys
import uuid

import boto3
import openai
from PIL import Image
import pymongo

# only local environment
import os

from botocore.exceptions import ClientError
# Define AWS settings
REGION = "ap-northeast-1"

SECRET_NAME = "openai_secret"

# Define ChatGPT 4o vision settings
BASE_PROMPT = [
    {
        "role": "system",
        "content": "画像を読み取り、それに相応しいtitleと画像から類推される状況をユーモラスに評論し、commentを作成してください"},
    {
        "role": "system",
        "content": "titleは30字以内、commentは500字以内に収めてください"
    },
    {
        "role": "system",
        "content": "回答は':'をデリミタとして'title:comment'のフォーマットを遵守してください"
    }
]

def test_img_encoding_b64(img_file) -> str:
    data64 = base64.b64encode(img_file).decode("utf-8")
    return data64

def img_encoding_b64(img_path):
    pass


def answer_request(imgdata64):
    # ToDo:キー未定義エラー時の挙動について考えておく。
    # secret_strings = get_secret()
    # API_KEY = secret_strings["API_ACCESS_KEY"]
    API_KEY = os.getenv('API_ACCESS_KEY')

    client = openai.OpenAI()

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=BASE_PROMPT + [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{imgdata64}"
                        }
                    }
                ]
            }
        ]
    )

    print(completion.choices[0].message)
    print(completion.usage)


def get_secret() -> dict:
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=REGION
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=SECRET_NAME
        )
    except ClientError as e:
        return {"result": e.response['Error']['code']}
    else:
        if 'SecretString' in get_secret_value_response:
            return get_secret_value_response['SecretString']
        else:
            return {"result": "strings is not be string, check your secret environment variable"}

def write_record():
    pass

def lambda_handler(event, context):
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    filename = event['Records'][0]['s3']['object']['key']

# for local test
if __name__ == '__main__':
    print('hello world')
