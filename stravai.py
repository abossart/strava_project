import pandas as pd
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_community.llms import OpenAI
import os
from dotenv import load_dotenv

dotenv_path='../secret/.env'
load_dotenv(dotenv_path)

# Hugging Face API token (set up your token at https://huggingface.co/settings/tokens)
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

# Hugging Face LLM Setup
def setup_huggingface_llm():
    from langchain.llms import HuggingFaceHub
    llm = HuggingFaceHub(
        #repo_id="tiiuae/falcon-7b-instruct",  # A lightweight instruct model
        repo_id="lmsys/vicuna-7b-v1.5",
        model_kwargs={"temperature": 0.7, "max_length": 512},
        huggingfacehub_api_token=HUGGINGFACE_API_KEY,
    )
    return llm

# Load CSV data into a DataFrame
def load_csv_data(file_path):
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    else:
        raise FileNotFoundError(f"CSV file '{file_path}' not found.")

# Query data using an AI model
def query_data_with_openai(file_path, query):
    try:
        # Load data into a Pandas DataFrame
        print("loading data")
        df = load_csv_data(file_path)
        print("data loaded")
        # Load environment variables from .env file

        openai_api_key = os.getenv("OPENAI_API_KEY")
        # Initialize the LLM
        llm = OpenAI(model="gpt-4o-mini", temperature=0, api_key=openai_api_key)

        # Create an agent for querying the DataFrame
        agent = create_pandas_dataframe_agent(llm, df, allow_dangerous_code=True, verbose=True)

        # Execute the query
        response = agent.run(query)
        return response
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Query the data
def query_data_with_huggingface(file_path, query):
    try:
        # Load data into a Pandas DataFrame
        df = load_csv_data(file_path)

        # Set up the Hugging Face LLM
        llm = setup_huggingface_llm()

        # Create an agent for querying the DataFrame
        agent = create_pandas_dataframe_agent(llm, df, allow_dangerous_code=True, verbose=True)

        # Execute the query
        response = agent.run(query)
        return response
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == "__main__":
    # Uncomment if data retrieval is needed
    # get_activities_for_2024()

    ai_provider = 'hugging'
    CSV_FILE = 'activities.csv'

    if ai_provider == 'hugging':
        # Example Queries
        query_1 = "Question: What are the names of shoes I used in my running activities this year?"
        query_2 = "Question: How many commute rides did I make in 2023, and what percentage of all rides does it represent?"

        print("Query 1 Response:")
        print(query_data_with_huggingface(CSV_FILE, query_1))

        #print("\nQuery 2 Response:")
        #print(query_data_with_huggingface(CSV_FILE, query_2))
    '''elif ai_provider == 'openAI':

        
        # Example: Query AI about the data
        query = "What are the names of shoes I used in my running activities this year?"
        result = query_data_with_openai(CSV_FILE, query)
        print(result)

        query = "How many commute rides did I do in 2023, and what percentage of all rides does it represent?"
        result = query_data_with_openai(CSV_FILE, query)
        print(result)'''