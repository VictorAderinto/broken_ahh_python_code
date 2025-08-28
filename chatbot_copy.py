import cohere
import json
import re
import numpy as np
import aiofiles
import json
import subprocess
import pandas as pd
import os
import json
import traceback
import logging

# from cohere.core.api_error import ApiError  # confirm the correct path
from cohere import UnprocessableEntityError

from input_validation import is_valid_date, is_valid_location, get_normalized_address, validate_full_phone_number, \
    suggest_typo_correction
from question_relationship import skipped_questions

# Specify the path to your JSON file
file_path_questions = 'trainning/questions_file_updated.json'
output_path = 'trainning/immigration_data_reduced.json'

# Open and load the JSON data
with open(file_path_questions, 'r', encoding='utf-8') as file:
    questions = json.load(file)

co = cohere.ClientV2(
    "geVCM43IEeDluUKP5YHEZnD8UxTd4DBH0t5gWUsp"
)

# Load the embeddings
doc_emb = np.load("others/doc_embeddings.npy")

with open(output_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

system_message = """
You are a form validation assistant. Please follow these strict rules:
1. You will be given a question and the user's response.
2. You must classify the response as one of:
   - VALID: [extracted answer]
   - QUESTION: [user's question]
   - INVALID: [reason or empty string]
3. DO NOT provide explanations or any extra text outside of the above formats.
4. DO NOT include line breaks or markdown formatting.

Examples:
- Q: What is your name? A: John → VALID: John
- Q: What is your age? A: What do you mean by age? → QUESTION: What do you mean by age?
- Q: What is your email? A: idk → INVALID: Please provide a valid email address.

Respond ONLY with one of: VALID: <answer>, INVALID: <reason>, or QUESTION: <question>.
"""


# Updated Version
def validate_with_llm(chat_history):
    try:
        # Defensive check
        if not chat_history or not any(msg['role'] == 'user' and msg['content'].strip() for msg in chat_history):
            raise ValueError("Chat history is empty or missing user input.")

        response = co.chat(
            model="command-a-03-2025",
            messages=chat_history,
        )
        output_text = response.message.content[0].text.strip()

        match = re.match(r'^(VALID|INVALID|QUESTION):\s*(.*)$', output_text)
        if match:
            return {"status": match.group(1).strip(), "value": match.group(2).strip()}
        else:
            # Retry logic
            chat_history.append({
                "role": "system",
                "content": "Please respond strictly in the required format: VALID: <answer>, INVALID: <reason>, or QUESTION: <question>."
            })
            response = co.chat(model="command-a-03-2025", messages=chat_history)
            output_text = response.message.content[0].text.strip()
            match = re.search(r'^(VALID|INVALID|QUESTION):\s*(.*)$', output_text)
            if match:
                return {"status": match.group(1).strip(), "value": match.group(2).strip()}
            else:
                return {"status": "INVALID", "value": "Model failed to parse response."}

    except UnprocessableEntityError as e:
        logging.error("422 Unprocessable Entity: Invalid message history sent to Cohere chat.")
        logging.error(json.dumps(chat_history, indent=2))  # Log messages for inspection
        print("⚠️ LLM could not generate a valid response. Please rephrase your input or check message format.")
        return {"status": "INVALID", "value": "LLM failed to process input. Please try again."}


def call_llm(messages, last_question):
    # print(messages)
    # print(last_question)
    search_queries = []
    query_gen_tool = [
        {
            "type": "function",
            "function": {
                "name": "internet_search",
                "description": "Returns a list of relevant document snippets for a textual query retrieved from the internet",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "a list of queries to search the internet with.",
                        }
                    },
                    "required": ["queries"],
                },
            },
        }
    ]

    instructions = "Write a search query that will find helpful information for answering the user's question accurately. If you need more than one search query, write a list of search queries. If you decide that a search is very unlikely to find information that would be useful in constructing a response to the user, you should instead directly answer."
    # Generate search queries (if any)

    messages.append({"role": "system", "content": instructions})
    res = co.chat(
        model="command-a-03-2025",
        messages=messages,
        tools=query_gen_tool,
    )
    if res.message.tool_calls:
        for tc in res.message.tool_calls:
            queries = json.loads(tc.function.arguments)["queries"]
            search_queries.extend(queries)

    if len(search_queries) == 0:
        query = "Explain this question in further detail to the user: " + last_question
        search_queries.append(query)

    query_emb = co.embed(
        model="embed-v4.0",
        input_type="search_query",
        texts=search_queries,
        embedding_types=["float"],
    ).embeddings.float

    # doc_emb = np.array(doc_emb)
    # Compute dot product similarity and display results
    n = 5
    scores = np.dot(query_emb, np.transpose(doc_emb))[0]
    max_idx = np.argsort(-scores)[:n]

    retrieved_documents = [data[item] for item in max_idx]

    # Rerank the documents
    results = co.rerank(
        model="rerank-v3.5",
        query=search_queries[0],
        documents=[doc["data"] for doc in retrieved_documents],
        top_n=2,
    )

    reranked_documents = [
        retrieved_documents[result.index] for result in results.results
    ]

    messages = [{"role": "user", "content": search_queries[0]}]

    # Generate the response
    response = co.chat(
        model="command-a-03-2025",
        messages=messages,
        documents=reranked_documents,
    )

    # Display the response
    result = response.message.content[0].text
    return result


def find_dli(school_name, city_name):
    df = pd.read_excel("trainning/School Information.xlsx")
    result = df[
        (df['School'].str.strip().str.lower() == school_name.strip().lower()) &
        (df['City'].str.strip().str.lower() == city_name.strip().lower())
        ]

    if not result.empty:
        return result['DLI #'].unique().tolist()
    else:
        return "No match found."

def fill_pdf(answers):
    form_data = list(answers.values())

    # Path to the compiled C# executable
    exe_path_imm1294 = "C:/Users/Victor/Downloads/Immigrate.AI/Immigrate.AI/imm1294.exe"
    exe_path_imm5406 = "C:/Users/Victor/Downloads/Immigrate.AI/Immigrate.AI/imm5406.exe"
    exe_path_imm5646 = "C:/Users/Victor/Downloads/Immigrate.AI/Immigrate.AI/imm5646.exe"
    exe_path_imm5409 = "C:/Users/Victor/Downloads/Immigrate.AI/Immigrate.AI/imm5409.exe"
    exe_path_imm0104 = "C:/Users/Victor/Downloads/Immigrate.AI/Immigrate.AI/imm0104.exe"

    subprocess.run([exe_path_imm5406] + form_data)
    subprocess.run([exe_path_imm1294] + form_data)
    subprocess.run([exe_path_imm5646] + form_data)
    subprocess.run([exe_path_imm5409] + form_data)
    subprocess.run([exe_path_imm0104] + form_data)

def is_immigration_question(text):
    # Simple keyword-based classifier; you can expand this as needed
    immigration_keywords = [
        "visa", "permit", "immigration", "study", "work", "canada", "passport", "citizenship",
        "application", "form", "dli", "refused", "entry", "status", "marital", "spouse"
    ]
    text_lower = text.lower()
    return any(word in text_lower for word in immigration_keywords)

def general_llm(messages):
    # Use the same LLM but with a general prompt
    general_prompt = "You are a helpful assistant. Answer the user's question clearly and concisely."
    messages = [{"role": "system", "content": general_prompt}] + messages
    response = co.chat(
        model="command-a-03-2025",
        messages=messages,
    )
    return response.message.content[0].text.strip()

# logging.basicConfig(level=logging.INFO, filename='form_debug.log', filemode='w',
#                     format='%(asctime)s - %(levelname)s - %(message)s')
def chat_step(state: dict, user_input: str) -> dict: 

    answers = state.get("answers", {})
    messages = state.get("messages", [])
    question_index = state.get("question_index", 0)
    skip = state.get("skip", 0)
    attempt_counter = state.get("attempt_counter", {})

    try:
        if not messages:
            messages.append({"role": "system", "content": system_message})

        # Handle skipping logic
        while skip > 0:
            question_index += 1
            skip -= 1

        if question_index >= len(questions):
            return {
                "reply": "✅ Form Completed!",
                "state": {
                    "answers": answers,
                    "messages": messages,
                    "question_index": question_index,
                    "skip": skip,
                    "attempt_counter": attempt_counter
                },
                "done": True
            }
        
        q = questions[question_index]
        field = q['field']
        attempt_counter[field] = attempt_counter.get(field, 0) + 1

        # Prompt OVERRIDE after 3 failed attempts
        if attempt_counter[field] > 2 and user_input != "OVERRIDE":
            attempt_counter[field] = 0  # reset counter
            return {
                "reply": "⚠️ You've tried several times. If you'd like to skip validation and enter your answer as-is, type 'OVERRIDE' (case-sensitive).",
                "state": {
                    **state,
                    "attempt_counter": attempt_counter
                },
                "done": False
            }

        # Special: DLI lookup
        if field == 'school_dli#':
            answers[field] = find_dli(answers.get('school_name', ''), answers.get('school_city', ''))
            return _next_step_response(answers, messages, question_index + 1, 0, attempt_counter)

        # Special: Citizenship rule
        if field == 'travel_start_date' and 'chin' in answers.get('citizenship', '').lower():
            return _next_step_response(answers, messages, len(questions), 0, attempt_counter)

        # OVERRIDE path
        if user_input == "OVERRIDE":
            return {
                "reply": "✏️ Enter your answer exactly as you'd like it recorded:",
                "state": {
                    "answers": answers,
                    "messages": messages,
                    "question_index": question_index,
                    "skip": skip,
                    "attempt_counter": attempt_counter,
                    "override_mode": True
                },
                "done": False
            }

        # If coming from override input
        if state.get("override_mode"):
            answers[field] = user_input
            return _next_step_response(answers, messages, question_index + 1, 0, attempt_counter)

            # Handle location/date/phone question detection
        
        # Handle location/date/phone question detection
        handled, continue_loop = handle_loc_date_phone_question(q, user_input, state["messages"])
        if handled and continue_loop:
            return {"reply": None, "state": state, "done": False}
    
        # Answer with options validation
        option_match = re.search(r'\(([^)]+)\)', q['text'], flags=re.IGNORECASE)
        if option_match and not user_input.endswith('?') and "date" not in q['field'].lower():
            raw_options = [opt.strip() for opt in re.split(r'[,/]', option_match.group(1))]
            raw_options = [opt for opt in raw_options if opt.lower() != 'e.g.']
            allowed_options_lower = [opt.lower() for opt in raw_options]
            if user_input.lower() not in allowed_options_lower:
                return {
                    "reply": f"❌ Please enter one of the valid options: {' or '.join(raw_options)} \
                        ❓ Or ask a follow-up question for clarification. Make sure to end your question with a question mark (?)",
                    "state": state,
                    "done": False
                }

        # Date field special validation
        if "date" in q['field']:
            no_future_allowed = q['field'] in ['date_of_birth', 'date of birth', 'passport_issue_date']
            no_past_allowed = 'expiry' in q['field'].lower()
            is_valid, result = is_valid_date(user_input, no_future_allowed=no_future_allowed, no_past_allowed=no_past_allowed)
            if not is_valid:
                return {"reply": f"❌ {result}", "state": state, "done": False}
            else:
                user_input = result.strftime('%Y-%m-%d')

        # Address normalization
        address_suffixes = ["_address", "_city", "_country", "_postal_code"]
        if any(q['field'].endswith(suffix) for suffix in address_suffixes):
            normalized_input = get_normalized_address(user_input, q['field'])
            if not normalized_input:
                return {"reply": "❌ Couldn't validate the address. Try again.", "state": state, "done": False}
            else:
                user_input = normalized_input

        # Phone validation
        phone_fields = ['_phone_country_code', '_phone_number', '_phone_extension', '_full_phone_number']
        if any(q['field'].endswith(suffix) for suffix in phone_fields):
            answers[q['field']] = user_input
            is_valid_phone, full_phone, fields_to_clear = validate_full_phone_number(answers, q['field'])
            if not is_valid_phone:
                print("❌ The phone number is invalid. Please re-enter the phone information.")
                for field in fields_to_clear:
                    answers[field] = ''
                return {
                    "reply": "❌ Invalid phone number. Please re-enter.",
                    "state": state,
                    "done": False
                }

        if user_input.endswith('?'):
            messages.append({"role": "system", "content": q['text']})
            messages.append({"role": "user", "content": user_input})

            result = validate_with_llm(messages)

            if result['status'] == "VALID":
                answers[q['field']] = result['value']
                messages.append({"role": "assistant", "content": result['value']})
                skip = skipped_questions(q['field'], answers)
                return _next_step_response(answers, messages, question_index + 1 + skip, 0, attempt_counter)
            
            elif result['status'] == "INVALID":
                return {
                    "reply": "❌ That wasn't valid. Please try again or ask a clarifying question.",
                    "state": state,
                    "done": False
                }

            elif result['status'] == "QUESTION":
                user_question = messages[-1]['content']
                if is_immigration_question(user_question):
                    response = call_llm(messages, messages[-2]['content'])
                else:
                    general_context = [
                        {"role": "system", "content": f"The user was asked: {q['text']}"},
                        {"role": "user", "content": user_question}
                    ]
                    response = general_llm(general_context)
                return {
                    "reply": response,
                    "state": state,
                    "done": False
                }
        else:
            if len(user_input.split()) <= 10:
                corrections = suggest_typo_correction(user_input)
                if corrections:
                    suggestions = ', '.join([f"'{w}' → '{c}'" for w, c in corrections])
                    return {
                    "reply": f"🤔 Did you mean: {suggestions}? Type your corrected input.",
                    "state": state,
                    "done": False
                    }
            answers[q['field']] = user_input
            skip = skipped_questions(q['field'], answers)
            return _next_step_response(answers, messages, question_index + 1 + skip, 0, attempt_counter)

    except Exception as e:
        logging.error("🔥 Error in chat_step():")
        logging.error(traceback.format_exc())
        return {
            "reply": f"🔥 An internal error occurred: {e}",
            "state": state,
            "done": False
        }

"""Helper functions"""
def _next_step_response(answers, messages, question_index, skip, attempt_counter):
    if question_index >= len(questions):
        return {
            "reply": "✅ Form Completed!",
            "state": {
                "answers": answers,
                "messages": messages,
                "question_index": question_index,
                "skip": skip,
                "attempt_counter": attempt_counter
            },
            "done": True
        }

    return {
        "reply": questions[question_index]["text"],
        "state": {
            "answers": answers,
            "messages": messages,
            "question_index": question_index,
            "skip": skip,
            "attempt_counter": attempt_counter
        },
        "done": False
    }

def handle_loc_date_phone_question(q, user_input, messages):
    """
    Check if field is location/date/phone related and if user input ends with '?',
    treat input as a question and send to LLM for answer.

    Returns:
        handled (bool): True if handled as question and printed response.
        continue_loop (bool): True if caller should ask for input again.
    """
    is_loc_date_phone = (
            'location' in q['field'] or
            'date' in q['field'] or
            any(suffix in q['field'] for suffix in
                ['phone', '_phone_number', '_phone_country_code', '_phone_extension', '_full_phone_number'])
    )

    if is_loc_date_phone and user_input.strip().endswith('?'):
        messages.append({"role": "system", "content": q['text']})
        messages.append({"role": "user", "content": user_input})

        result = validate_with_llm(messages)

        if result['status'] == "QUESTION":
            user_question = messages[-1]['content']
            if is_immigration_question(user_question):
                response = call_llm(messages, messages[-2]['content'])
            else:
                general_context = [
                    {"role": "system", "content": f"The user was asked: {q['text']}"},
                    {"role": "user", "content": user_question}
                ]
                response = general_llm(general_context)
            print(response)
            return True, True  # handled, continue asking input
        else:
            # Not a question response, fall through to normal processing
            return False, False

    return False, False

def save_state(state, filename="state.json"):
    with open(filename, "w") as f:
        json.dump(state, f)

def load_state(filename="state.json"):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {"answers": {}, "messages": [], "question_index": 0, "skip": 0}

if __name__ == "__main__":
    state = load_state()
    if state["question_index"] < len(questions):
        print(questions[state["question_index"]]["text"])

    while True:
        user_input = input("> ")
        if user_input.lower() in ["exit", "quit"]:
            save_state(state)
            print("💾 Progress saved. You can resume later.")
            break

        result = chat_step(state, user_input)
        print(result["reply"])
        state = result["state"]

        save_state(state)  # Save after each step

        if result["done"]:
            print("🎉 All questions answered.")
            os.remove("state.json")  # Clear save file
            break
