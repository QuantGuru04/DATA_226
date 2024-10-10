# -*- coding: utf-8 -*-
"""HW-5_226.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1pRc_MSaeqlYxNSwsXszq6EuU2vcV8ruy
"""

from airflow import DAG
from airflow.models import Variable
from airflow.decorators import task
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from datetime import timedelta, datetime
import requests

# Define default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

# Helper function to establish Snowflake connection
def get_snowflake_connection():
    hook = SnowflakeHook(snowflake_conn_id='my_snowflake_conn')
    return hook.get_conn()

# Task 1: Extract the stock symbol
@task
def extract_symbol(symbol):
    return symbol

# Task 2: Fetch stock prices for the last 90 days from Alpha Vantage API
@task
def fetch_last_90_days_data(symbol):
    vantage_api_key = Variable.get('vantage_api_key')
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={vantage_api_key}'
    response = requests.get(url)
    data = response.json()


    if "Time Series (Daily)" in data:
        results = []
        for date, stock_info in data["Time Series (Daily)"].items():
            stock_info['date'] = date
            results.append(stock_info)
        return results
    else:
        raise ValueError(f"Error fetching data for {symbol}: {data}")

# Task 3: Create the Snowflake table if it does not exist
@task
def create_stock_price_table():
    create_table_query = """
        CREATE OR REPLACE TABLE RAW_DATA.stock_price (
            open FLOAT,
            high FLOAT,
            low FLOAT,
            close FLOAT,
            volume BIGINT,
            date DATE PRIMARY KEY
        )
    """
    conn = get_snowflake_connection()

    with conn.cursor() as cur:
        try:
            # Set the database and schema
            cur.execute("USE DATABASE MY_DB")
            cur.execute("USE SCHEMA RAW_DATA")
            cur.execute(create_table_query)
            print("Table created or replaced successfully.")
        except Exception as e:
            print(f"Error occurred while creating the table: {e}")
            raise
        finally:
            conn.close()

# Task 4: Insert stock data records into Snowflake
@task
def load_stock_data_to_snowflake(data):
    insert_query = """
        INSERT INTO raw_data.stock_price (open, high, low, close, volume, date)
        VALUES (%(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(date)s)
    """

    conn = get_snowflake_connection()

    with conn.cursor() as cur:
        try:
            # Set the database and schema
            cur.execute("USE DATABASE MY_DB")
            cur.execute("USE SCHEMA RAW_DATA")

            # Insert each record
            for record in data:
                record_data = {
                    'open': record['1. open'],
                    'high': record['2. high'],
                    'low': record['3. low'],
                    'close': record['4. close'],
                    'volume': record['5. volume'],
                    'date': record['date']
                }
                cur.execute(insert_query, record_data)

            print("Data loaded successfully into Snowflake.")
        except Exception as e:
            print(f"Error occurred while inserting records: {e}")
            raise
        finally:
            conn.close()

# Define the DAG
with DAG(
    dag_id='stock_data_pipeline',
    default_args=default_args,
    start_date=datetime(2024, 10, 9),
    catchup=False,
    schedule_interval='@daily',
    tags=['stock', 'ETL'],
) as dag:

    # Define the stock symbol
    symbol = 'IBM'

    # Define task pipeline
    raw_symbol = extract_symbol(symbol)
    stock_data = fetch_last_90_days_data(raw_symbol)
    create_stock_price_table()
    load_stock_data_to_snowflake(stock_data)