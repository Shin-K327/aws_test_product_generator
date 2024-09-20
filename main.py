import base64
import datetime
import re
import uuid

import boto3
import openai

# only local environment
import os

from openai.types.chat import ChatCompletionMessage
from typing_extensions import Optional

import local_settings

from botocore.exceptions import ClientError
# Define AWS settings
REGION = "ap-northeast-1"
TABLE_NAME = os.getenv("TABLE_NAME")
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
        "content": "回答は'title:comment'のフォーマットを遵守してください"
    }
]

def img_encoding_b64(img_file) -> str:
    data64 = base64.b64encode(img_file).decode("utf-8")
    return data64

def answer_request(imgdata64:str, ext:str)-> str | None:
    # ToDo:キー未定義エラー時の挙動について考えておく。
    # secret_strings = get_secret()
    # API_KEY = secret_strings["API_ACCESS_KEY"]

    client = openai.OpenAI()

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=BASE_PROMPT + [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{ext};base64,{imgdata64}"
                            }
                        }
                    ]
                }
            ]
        )
    except openai.APIStatusError as e:
        return None
    else :
        return completion.choices[0].message.__repr__()

# Deprecate
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

def test_create_table():
    dbclient = boto3.client('dynamodb', endpoint_url="http://localhost:8000")
    TABLE_NAME = local_settings.TEST_TABLE_NAME

    table = dbclient.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
            {"AttributeName": "created_date", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "created_date", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST",
    )

def write_record(title, comment, s3_path):
    dbclient = boto3.client('dynamodb')

    try:
        dbclient.put_item(TableName=TABLE_NAME, Item={
            "id": {"S": str(uuid.uuid4())},
            "created_date": {"S": datetime.datetime.now().strftime("%Y-%m-%d")},
            "title": {"S": title},
            "comment": {"S": comment},
            "path": {"S": s3_path}
        })
    except ClientError as e:
        raise e

def _abort_process(s3_bkt_name, s3_obj_key):
    bucket_client = boto3.client('s3')
    bucket_client.delete_object(s3_bkt_name, s3_obj_key)
    exit(1)

def lambda_handler(event, context):
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    filename = event['Records'][0]['s3']['object']['key']

    ext_pattern = '(jpe?g|png|gif|bmp)'
    file_extension = os.path.splitext(filename)[1][1:]

    ext_check = re.compile(ext_pattern)
    if ext_check.match(file_extension) is None: _abort_process(bucket_name, filename)

    s3_client = boto3.client('s3')
    img_data = s3_client.get_object(Bucket=bucket_name, Key=filename).read()

    b64_data = img_encoding_b64(img_data)
    response = answer_request(b64_data, file_extension)

    res_fmt = '^.+:.+$'
    res_check = re.compile(res_fmt)

    if res_check.match(response) is None: _abort_process(bucket_name, filename)

    title, comment, *other = response.split(':')
    public_path = f'https://{bucket_name}.s3.{REGION}.amazonaws.com/{filename}'

    try:
        write_record(title, comment, public_path)
    except ClientError as e:
        _abort_process(bucket_name, filename)


# for local test
if __name__ == '__main__':
    pass